#!/usr/bin/env python3
"""Monitor Azure OpenAI batch jobs using the OpenAI Python SDK."""

from dotenv import load_dotenv

load_dotenv()

import argparse
import logging
import os
import time
from datetime import datetime, timezone

from openai import OpenAI, OpenAIError


ACTIVE_STATUSES = {"validating", "in_progress", "finalizing"}
DEFAULT_MAX_AGE_HOURS = 24.0
DEFAULT_POLL_INTERVAL_SECONDS = 3600


def azure_base_url(endpoint: str) -> str:
    """Convert an Azure resource endpoint to an OpenAI v1 base URL."""
    endpoint = endpoint.rstrip("/")
    if not endpoint.endswith("/openai/v1"):
        endpoint = f"{endpoint}/openai/v1"
    return f"{endpoint}/"


def scan_batches(client: OpenAI, max_age_hours: float, dry_run: bool) -> tuple[int, int]:
    """List every batch and cancel active batches older than the age limit."""
    checked = 0
    cancelled = 0
    now = datetime.now(timezone.utc)

    # The SDK automatically requests subsequent cursor pages during iteration.
    for batch in client.batches.list(limit=100):
        checked += 1
        status = batch.status.lower()
        created_at = datetime.fromtimestamp(batch.created_at, tz=timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600

        logging.info("batch=%s status=%s age=%.2fh", batch.id, status, age_hours)

        if status not in ACTIVE_STATUSES or age_hours <= max_age_hours:
            continue

        if dry_run:
            logging.warning(
                "DRY RUN: would cancel batch=%s (status=%s, age=%.2fh)",
                batch.id,
                status,
                age_hours,
            )
            continue

        try:
            result = client.batches.cancel(batch.id)
        except OpenAIError:
            logging.exception("could not cancel batch=%s", batch.id)
            continue

        cancelled += 1
        logging.warning(
            "cancel requested for batch=%s (age=%.2fh, new_status=%s)",
            batch.id,
            age_hours,
            result.status,
        )

    logging.info("scan complete: checked=%d cancel_requests=%d", checked, cancelled)
    return checked, cancelled


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-hours",
        type=positive_float,
        default=float(os.getenv("BATCH_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS)),
        help="cancel active batches older than this many hours (default: 24)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="keep polling; without this flag the script performs one scan",
    )
    parser.add_argument(
        "--poll-seconds",
        type=positive_float,
        default=float(
            os.getenv("BATCH_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS)
        ),
        help="seconds between scans in watch mode (default: 3600)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report overdue jobs without cancelling"
    )
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    client = OpenAI(
        base_url=azure_base_url(required_env("AZURE_OPENAI_ENDPOINT")),
        api_key=required_env("AZURE_OPENAI_API_KEY"),
        timeout=30.0,
    )

    while True:
        try:
            scan_batches(client, args.max_age_hours, args.dry_run)
        except OpenAIError:
            logging.exception("batch scan failed")
            if not args.watch:
                raise SystemExit(1)

        if not args.watch:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("monitor stopped")
