#!/usr/bin/env python3
"""Replay prompts captured in user_logs.txt against an Azure OpenAI deployment."""

import argparse
import ast
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from openai import OpenAI
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *_, **__: None  # type: ignore

LOG_SAMPLE_MARKER = "Evaluation completed successfully: "
TARGET_MARKER = "Running evaluation target:"


def safe_literal_loads(value: str):
    """Parse Python- or JSON-like literals without raising."""
    for loader in (ast.literal_eval, json.loads):
        try:
            return loader(value)
        except Exception:
            continue
    return None


def resolve_completion_model(completion: Any) -> Optional[str]:
    """Return the model string from a ChatCompletion response if available."""
    if completion is None:
        return None

    raw_value = getattr(completion, "model", None)
    if raw_value:
        return str(raw_value)

    for attr in ("model_dump", "to_dict"):
        if not hasattr(completion, attr):
            continue
        try:
            data = getattr(completion, attr)()
        except Exception:
            continue
        if isinstance(data, dict) and data.get("model"):
            return str(data["model"])

    if isinstance(completion, dict) and completion.get("model"):
        return str(completion["model"])

    return None


def extract_eval_target_defaults(log_path: Path) -> Dict[str, Optional[float]]:
    """Extract system prompt and sampling params from the evaluation log if present."""
    defaults: Dict[str, Optional[float]] = {
        "system": None,
        "temperature": None,
        "top_p": None,
        "model": None,
    }
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return defaults
    for line in lines:
        if TARGET_MARKER not in line:
            continue
        payload = line.split(TARGET_MARKER, 1)[1].strip()
        config = safe_literal_loads(payload)
        if not isinstance(config, dict):
            continue
        input_messages = config.get("input_messages") or {}
        template = input_messages.get("template") or []
        for entry in template:
            if entry.get("role") == "system":
                defaults["system"] = entry.get("content")
                break
        sampling = config.get("sampling_params") or {}
        defaults["temperature"] = sampling.get("temperature")
        defaults["top_p"] = sampling.get("top_p")
        defaults["model"] = sampling.get("model")
        break
    return defaults


def normalize_message_content(content: Any) -> str:
    """Return the user-facing text from a content field."""
    if content is None:
        return ""
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    content_str = content if isinstance(content, str) else str(content)
    parsed = safe_literal_loads(content_str)
    if isinstance(parsed, dict):
        if "query" in parsed:
            return parsed["query"]
        if "prompt" in parsed:
            return parsed["prompt"]
        return json.dumps(parsed, ensure_ascii=False)
    if isinstance(parsed, list):
        return json.dumps(parsed, ensure_ascii=False)
    if isinstance(parsed, str):
        return parsed
    return content_str


def extract_examples(log_path: Path) -> List[List[Dict[str, str]]]:
    """Return deduplicated chat message lists discovered in the log."""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return []
    examples: List[List[Dict[str, str]]] = []
    seen_prompts = set()
    for line in lines:
        if LOG_SAMPLE_MARKER not in line:
            continue
        payload = line.split(LOG_SAMPLE_MARKER, 1)[1].strip()
        data = safe_literal_loads(payload)
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if not key.endswith("_sample_input"):
                continue
            convo = safe_literal_loads(value)
            if not isinstance(convo, list):
                continue
            messages: List[Dict[str, str]] = []
            for message in convo:
                role = message.get("role")
                content = message.get("content")
                if role is None or content is None:
                    continue
                normalized = normalize_message_content(content)
                messages.append({"role": role, "content": normalized})
            if not messages:
                continue
            user_text = "\n\n".join(
                msg["content"] for msg in messages if msg["role"] == "user"
            )
            if not user_text or user_text in seen_prompts:
                continue
            seen_prompts.add(user_text)
            examples.append(messages)
    return examples


def load_examples_from_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """Load chat prompts from a JSONL dataset."""
    examples: List[Dict[str, Any]] = []
    try:
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                payload = line.strip()
                if not payload:
                    continue
                data = safe_literal_loads(payload)
                if not isinstance(data, dict):
                    print(
                        f"Skipping line {line_number}: expected object, found {type(data).__name__}",
                        file=sys.stderr,
                    )
                    continue

                messages: List[Dict[str, str]] = []
                raw_messages = data.get("messages")
                if isinstance(raw_messages, list):
                    for raw_entry in raw_messages:
                        if not isinstance(raw_entry, dict):
                            continue
                        role = raw_entry.get("role")
                        content = raw_entry.get("content")
                        if role is None or content is None:
                            continue
                        normalized = normalize_message_content(content)
                        messages.append({"role": role, "content": normalized})
                else:
                    system_content = data.get("system")
                    if system_content:
                        messages.append(
                            {
                                "role": "system",
                                "content": normalize_message_content(system_content),
                            }
                        )
                    user_content = None
                    for field in ("query", "prompt", "input", "content"):
                        if field in data and data[field] not in (None, ""):
                            user_content = data[field]
                            break
                    if user_content is not None:
                        normalized_user = normalize_message_content(user_content)
                        messages.append({"role": "user", "content": normalized_user})

                if not messages:
                    print(
                        f"Skipping line {line_number}: no usable messages found",
                        file=sys.stderr,
                    )
                    continue

                example: Dict[str, Any] = {
                    "messages": messages,
                    "id": data.get("id"),
                }
                for key in ("model", "metadata"):
                    if key in data:
                        example[key] = data[key]
                examples.append(example)
    except FileNotFoundError:
        return []
    return examples


def utc_timestamp() -> str:
    """Return a UTC timestamp in ISO 8601 format with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_examples(
    client: Optional[OpenAI],
    examples: Iterable[Dict[str, Any]],
    *,
    system_prompt: Optional[str],
    temperature: Optional[float],
    top_p: Optional[float],
    default_model: str,
    sleep_seconds: float,
    dry_run: bool,
    stop_on_error: bool,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for index, example in enumerate(examples, 1):
        if isinstance(example, dict):
            example_messages = example.get("messages", [])
            if not isinstance(example_messages, list):
                example_messages = []
            example_id = example.get("id")
            example_model = example.get("model")
            example_metadata = example.get("metadata")
        else:
            example_messages = example
            example_id = None
            example_model = None
            example_metadata = None

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for message in example_messages:
            role = message.get("role")
            content = message.get("content")
            if role is None or content is None:
                continue
            messages.append({"role": role, "content": content})

        request_model = str(example_model or default_model)
        if system_prompt:
            base_prompt = system_prompt
        else:
            base_prompt = None

        user_prompt = next(
            (msg["content"] for msg in messages if msg["role"] == "user"),
            None,
        )
        record: Dict[str, Any] = {
            "example_index": index,
            "input_id": example_id,
            "prompt": user_prompt,
            "messages": messages,
            "requested_model": request_model,
            "temperature": temperature,
            "top_p": top_p,
            "dry_run": dry_run,
            "requested_at": utc_timestamp(),
        }
        if example_model:
            record["override_model"] = example_model
        if base_prompt is not None:
            record["injected_system_prompt"] = base_prompt
        if example_metadata is not None:
            record["input_metadata"] = example_metadata

        print(f"\n=== Example {index} ===")
        if example_id is not None:
            print(f"Input ID: {example_id}")
        if user_prompt:
            print(f"Prompt: {user_prompt}")
        else:
            print("Prompt: <no user message found>")

        if dry_run:
            print("(dry run) Skipping API call.")
            records.append(record)
            continue
        if client is None:
            raise RuntimeError("API client not initialised; cannot run without --dry-run.")

        try:
            completion = client.chat.completions.create(
                model=request_model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
            )
        except Exception as exc:
            record["error"] = str(exc)
            record["error_type"] = exc.__class__.__name__
            print(f"Request failed: {exc}", file=sys.stderr)
            records.append(record)
            if stop_on_error:
                raise
            continue

        response_model = resolve_completion_model(completion)
        if response_model:
            print(f"Model (completion): {response_model}")
        choice = completion.choices[0]
        response_text = choice.message.content
        print("Response:")
        print(response_text)

        record["response"] = response_text
        record["finish_reason"] = getattr(choice, "finish_reason", None)
        record["completion_id"] = getattr(completion, "id", None)
        record["response_model"] = response_model
        usage = getattr(completion, "usage", None)
        if usage is not None:
            try:
                record["usage"] = usage.model_dump()
            except AttributeError:
                record["usage"] = dict(usage)
        record["completed_at"] = utc_timestamp()

        records.append(record)

        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay prompts captured in user_logs.txt using the OpenAI SDK."
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("user_logs.txt"),
        help="Path to the log file containing evaluation examples.",
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=Path('input.jsonl'),
        help="Optional JSONL file containing chat prompts to replay.",
    )
    parser.add_argument(
        "--endpoint",
        default="https://jacwang-2603-resource.openai.azure.com/openai/v1/",
        help="Azure OpenAI endpoint base URL.",
    )
    parser.add_argument(
        "--deployment",
        default="model-router-quality",
        help="Azure OpenAI deployment name to target.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key to use. Defaults to OPENAI_API_KEY/AZURE_OPENAI_API_KEY env vars if omitted.",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="Optional system prompt to prepend to every request.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature for the requests.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help="Nucleus sampling top_p value.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of examples to run.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between calls.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, only print the prompts without calling the API.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Abort on first failed request when not in dry-run mode.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to write the timestamped dataset file.",
    )
    parser.add_argument(
        "--output-prefix",
        default="batch_results",
        help="Filename prefix for the timestamped dataset file.",
    )
    return parser.parse_args()


def write_dataset(
    records: List[Dict[str, Any]],
    output_dir: Path,
    prefix: str,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{prefix}_{timestamp}.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    return output_path


def main() -> None:
    load_dotenv()
    args = parse_args()
    log_path: Path = args.log_path
    jsonl_path: Optional[Path] = args.input_jsonl
    if jsonl_path is None and not log_path.exists():
        print(f"Log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    defaults = extract_eval_target_defaults(log_path)
    system_prompt = args.system if args.system is not None else defaults.get("system")
    temperature = args.temperature if args.temperature is not None else (
        defaults.get("temperature") or 0.7
    )
    top_p = args.top_p if args.top_p is not None else (defaults.get("top_p") or 0.95)

    base_model = defaults.get("model") or args.deployment

    examples: List[Dict[str, Any]]
    if jsonl_path is not None:
        if not jsonl_path.exists():
            print(f"JSONL file not found: {jsonl_path}", file=sys.stderr)
            sys.exit(1)
        examples = load_examples_from_jsonl(jsonl_path)
        source_description = f"{jsonl_path}"
    else:
        raw_examples = extract_examples(log_path)
        examples = [{"messages": messages} for messages in raw_examples]
        source_description = f"{log_path}"

    if not examples:
        print(f"No examples found in {source_description}.", file=sys.stderr)
        sys.exit(1)
    if args.limit is not None:
        examples = examples[: args.limit]
    client: Optional[OpenAI] = None
    if not args.dry_run:
        client = OpenAI(base_url=args.endpoint, api_key=args.api_key)
    records = run_examples(
        client,
        examples,
        system_prompt=system_prompt,
        temperature=temperature,
        top_p=top_p,
        default_model=base_model,
        sleep_seconds=args.sleep,
        dry_run=args.dry_run,
        stop_on_error=args.stop_on_error,
    )
    output_path = write_dataset(records, args.output_dir, args.output_prefix)
    print(f"\nWrote dataset to {output_path}")


if __name__ == "__main__":
    main()
