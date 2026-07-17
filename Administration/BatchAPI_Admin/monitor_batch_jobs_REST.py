#!/usr/bin/env python3
"""Monitor Azure OpenAI batch jobs and cancel jobs older than a limit."""

from dotenv import load_dotenv

load_dotenv()

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ACTIVE_STATUSES = {"validating", "in_progress", "finalizing"}
DEFAULT_MAX_AGE_HOURS = 24.0
DEFAULT_POLL_INTERVAL_SECONDS = 3600


class BatchApiClient:
    """Small client for the Azure OpenAI v1 Batch REST API."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        endpoint = endpoint.rstrip("/")
        if not endpoint.endswith("/openai/v1"):
            endpoint = f"{endpoint}/openai/v1"
        self.base_url = endpoint
        self.headers = {"api-key": api_key, "Content-Type": "application/json"}

    def _request(self, method: str, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=b"" if method == "POST" else None,
            headers=self.headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Batch API returned HTTP {exc.code} for {method} {path}: {details}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach the Batch API: {exc.reason}") from exc

    def list_batches(self) -> Iterator[dict[str, Any]]:
        """Yield every batch, following the API's cursor pagination."""
        after: str | None = None
        seen_cursors: set[str] = set()

        while True:
            query = {"limit": 100}
            if after:
                query["after"] = after
            payload = self._request("GET", f"batches?{urlencode(query)}")
            batches = payload.get("data", payload.get("value", []))

            if not isinstance(batches, list):
                raise RuntimeError("Batch API response did not contain a batch list")

            yield from batches

            if not payload.get("has_more") or not batches:
                return

            next_cursor = payload.get("last_id") or batches[-1].get("id")
            if not next_cursor or next_cursor in seen_cursors:
                raise RuntimeError("Batch API pagination did not return a new cursor")
            seen_cursors.add(next_cursor)
            after = next_cursor

    def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        safe_batch_id = quote(batch_id, safe="")
        return self._request("POST", f"batches/{safe_batch_id}/cancel")


def parse_timestamp(value: Any) -> datetime:
    """Parse epoch seconds or the ISO timestamps returned by Azure."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(f"Unsupported timestamp: {value!r}")


def scan_batches(
    client: BatchApiClient, max_age_hours: float, dry_run: bool
) -> tuple[int, int]:
    """Log all batch statuses and cancel active batches over the age limit."""
    checked = 0
    cancelled = 0
    now = datetime.now(timezone.utc)

    for batch in client.list_batches():
        checked += 1
        batch_id = str(batch.get("id", "<missing-id>"))
        status = str(batch.get("status", "unknown")).lower()

        try:
            created_at = parse_timestamp(batch.get("created_at"))
            age_hours = (now - created_at).total_seconds() / 3600
        except (TypeError, ValueError) as exc:
            logging.warning("batch=%s status=%s age=unknown (%s)", batch_id, status, exc)
            continue

        logging.info("batch=%s status=%s age=%.2fh", batch_id, status, age_hours)

        if status not in ACTIVE_STATUSES or age_hours <= max_age_hours:
            continue

        if dry_run:
            logging.warning(
                "DRY RUN: would cancel batch=%s (status=%s, age=%.2fh)",
                batch_id,
                status,
                age_hours,
            )
            continue

        try:
            result = client.cancel_batch(batch_id)
        except RuntimeError:
            logging.exception("could not cancel batch=%s", batch_id)
            continue
        cancelled += 1
        logging.warning(
            "cancel requested for batch=%s (age=%.2fh, new_status=%s)",
            batch_id,
            age_hours,
            result.get("status", "unknown"),
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
    client = BatchApiClient(
        endpoint=required_env("AZURE_OPENAI_ENDPOINT"),
        api_key=required_env("AZURE_OPENAI_API_KEY"),
    )

    while True:
        try:
            scan_batches(client, args.max_age_hours, args.dry_run)
        except RuntimeError:
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
