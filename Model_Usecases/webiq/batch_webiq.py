"""Run every query in a CSV file through WebIQ and save JSONL results."""

# ruff: noqa: I001

from dotenv import load_dotenv

load_dotenv()

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

import requests

from webiq_test import AUTH_METHODS, resolve_auth_credentials, search_web


DEFAULT_INPUT = Path("websearch_results (version 1).csv")
DEFAULT_OUTPUT = Path("webiq_batch_results.jsonl")


def read_queries(input_path: Path, query_column: str) -> list[tuple[int, str]]:
    """Read non-empty queries while retaining their one-based CSV row numbers."""
    with input_path.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if not reader.fieldnames or query_column not in reader.fieldnames:
            available = ", ".join(reader.fieldnames or []) or "none"
            raise ValueError(
                f"Column {query_column!r} was not found in {input_path}. "
                f"Available columns: {available}"
            )

        return [
            (row_number, query)
            for row_number, row in enumerate(reader, start=2)
            if (query := (row.get(query_column) or "").strip())
        ]


def completed_rows(output_path: Path) -> set[int]:
    """Return source rows already recorded in an existing JSONL output."""
    if not output_path.exists():
        return set()

    completed: set[int] = set()
    with output_path.open(encoding="utf-8") as output_file:
        for line_number, line in enumerate(output_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                completed.add(int(record["source_row"]))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid JSONL record at {output_path}:{line_number}"
                ) from exc
    return completed


def error_record(exc: requests.RequestException) -> dict[str, Any]:
    """Create a serializable API error without exposing request headers."""
    record: dict[str, Any] = {
        "status": "error",
        "error": str(exc),
    }
    if exc.response is not None:
        record["http_status"] = exc.response.status_code
        record["response_body"] = exc.response.text[:2000]
    return record


def run_batch(
    input_path: Path,
    output_path: Path,
    query_column: str,
    delay: float,
    resume: bool,
    auth_method: str = "auto",
) -> None:
    """Execute all CSV queries and write one result record per JSONL line."""
    if delay < 0:
        raise ValueError("Delay cannot be negative.")

    api_key, access_token = resolve_auth_credentials(auth_method)
    queries = read_queries(input_path, query_column)
    already_completed = completed_rows(output_path) if resume else set()
    pending = [item for item in queries if item[0] not in already_completed]
    file_mode = "a" if resume else "w"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"Processing {len(pending)} of {len(queries)} queries; "
        f"writing to {output_path}"
    )

    with requests.Session() as session, output_path.open(
        file_mode, encoding="utf-8"
    ) as output_file:
        for position, (source_row, query) in enumerate(pending, start=1):
            print(f"[{position}/{len(pending)}] CSV row {source_row}: {query[:80]}")
            record: dict[str, Any] = {
                "source_row": source_row,
                "query": query,
            }
            try:
                record.update(
                    status="ok",
                    response=search_web(
                        query,
                        print_result=False,
                        session=session,
                        access_token=access_token,
                        api_key=api_key,
                    ),
                )
            except requests.RequestException as exc:
                record.update(error_record(exc))

            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            output_file.flush()

            if delay and position < len(pending):
                time.sleep(delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run each CSV query through WebIQ and write JSONL output."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--query-column", default="prompt")
    parser.add_argument(
        "--auth",
        choices=sorted(AUTH_METHODS),
        default="auto",
        help="Authentication method (default: auto; API key when configured).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between API requests (default: 0.5).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append to the output and skip source rows already recorded.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_batch(
        input_path=args.input,
        output_path=args.output,
        query_column=args.query_column,
        delay=args.delay,
        resume=args.resume,
        auth_method=args.auth,
    )
