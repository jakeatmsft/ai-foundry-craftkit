#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "data" / "masked_content_safety_eval.jsonl"
DEFAULT_SEED_PROMPT_PATH = ROOT / "data" / "seed_prompt.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a masked-input probe against Azure OpenAI and report "
            "whether content filtering triggers for each test case."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help=f"Path to JSONL test cases (default: {DEFAULT_DATA_PATH})",
    )
    parser.add_argument(
        "--seed-prompt",
        type=Path,
        default=DEFAULT_SEED_PROMPT_PATH,
        help=f"Path to seed prompt JSON containing `system_prompt` (default: {DEFAULT_SEED_PROMPT_PATH})",
    )
    parser.add_argument(
        "--no-system-prompt",
        action="store_true",
        help="Skip loading/including the seed system prompt.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. Defaults to outputs/masked_content_safety_probe_<timestamp>.json",
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Invalid or missing `query` at {path}:{line_number}")
        case_id = payload.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            payload["id"] = f"case_{line_number}"
        cases.append(payload)

    if not cases:
        raise ValueError(f"No valid test cases found in {path}")
    return cases


def load_system_prompt(path: Path) -> str | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompt = payload.get("system_prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    return None


def extract_content_filter_result(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error", payload)
    if not isinstance(error, dict):
        return None
    innererror = error.get("innererror", {})
    if not isinstance(innererror, dict):
        return None
    content_filter_result = innererror.get("content_filter_result")
    if isinstance(content_filter_result, dict):
        return content_filter_result
    return None


def parse_message_for_content_filter(message: str) -> dict[str, Any] | None:
    if "content_filter_result" not in message:
        return None
    body = message.split(" - ", 1)[-1]
    for parser in (ast.literal_eval, json.loads):
        try:
            payload = parser(body)
        except (ValueError, SyntaxError, json.JSONDecodeError, TypeError):
            continue
        content_filter_result = extract_content_filter_result(payload)
        if content_filter_result is not None:
            return content_filter_result
    return None


def summarize_filtered_categories(content_filter_result: dict[str, Any] | None) -> list[str]:
    if not isinstance(content_filter_result, dict):
        return []
    categories: list[str] = []
    for category, details in content_filter_result.items():
        if isinstance(details, dict) and details.get("filtered") is True:
            categories.append(category)
    return categories


def response_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_case(
    client: OpenAI,
    model: str,
    case: dict[str, Any],
    system_prompt: str | None,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": str(case["query"])})

    try:
        completion = client.chat.completions.create(model=model, messages=messages)
        response_text = completion.choices[0].message.content or ""
        return {
            "id": case["id"],
            "description": case.get("description", ""),
            "query": case["query"],
            "filtered": False,
            "status_code": 200,
            "error_code": None,
            "content_filter_result": None,
            "filtered_categories": [],
            "response_received": True,
            "response_length": len(response_text),
            "response_sha256": response_fingerprint(response_text),
        }
    except APIStatusError as exc:
        payload: dict[str, Any] | None = None
        if exc.response is not None:
            try:
                payload = exc.response.json()
            except Exception:
                payload = None

        content_filter_result = extract_content_filter_result(payload)
        if content_filter_result is None:
            content_filter_result = parse_message_for_content_filter(str(exc))

        error_code = None
        if isinstance(payload, dict):
            error = payload.get("error", {})
            if isinstance(error, dict):
                error_code = error.get("code")

        filtered = bool(content_filter_result) or error_code == "content_filter"
        return {
            "id": case["id"],
            "description": case.get("description", ""),
            "query": case["query"],
            "filtered": filtered,
            "status_code": exc.status_code,
            "error_code": error_code,
            "content_filter_result": content_filter_result,
            "filtered_categories": summarize_filtered_categories(content_filter_result),
            "response_received": False,
            "response_length": 0,
            "response_sha256": None,
            "error_message": str(exc),
        }


def main() -> None:
    args = parse_args()
    load_dotenv()

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_DEPLOYMENT", model),
        )
        if not value
    ]
    if missing:
        raise EnvironmentError(f"Missing required environment variable(s): {', '.join(missing)}")

    cases = load_cases(args.data)
    system_prompt = None if args.no_system_prompt else load_system_prompt(args.seed_prompt)

    client = OpenAI(api_key=api_key, base_url=endpoint)
    results = [run_case(client=client, model=model, case=case, system_prompt=system_prompt) for case in cases]

    filtered_count = sum(1 for result in results if result["filtered"])
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(results),
        "filtered_cases": filtered_count,
        "unfiltered_cases": len(results) - filtered_count,
    }

    print("Masked input content safety probe")
    print(f"Total: {summary['total_cases']} | Filtered: {summary['filtered_cases']} | Unfiltered: {summary['unfiltered_cases']}")
    for result in results:
        categories = ",".join(result["filtered_categories"]) if result["filtered_categories"] else "-"
        print(
            f"- {result['id']}: filtered={result['filtered']} status={result['status_code']} "
            f"categories={categories} response_received={result['response_received']}"
        )

    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"masked_content_safety_probe_{timestamp}.json"
    else:
        output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary,
        "config": {
            "data": str(args.data.resolve()),
            "seed_prompt": None if args.no_system_prompt else str(args.seed_prompt.resolve()),
            "model": model,
            "endpoint": endpoint,
        },
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
