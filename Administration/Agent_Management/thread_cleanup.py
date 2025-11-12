# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""Remove Azure AI threads whose most recent message predates the cutoff.

Usage:
    python thread_cleanup.py [--before-date YYYY-MM-DD] [--days N] [--dry-run]

    When no explicit ``--before-date`` is supplied the script defaults to 30 days
    before the current time in UTC. Threads with no messages are skipped.

Set up:
    pip install azure-ai-projects azure-ai-agents azure-identity python-dotenv
    export PROJECT_ENDPOINT=...
    export MODEL_DEPLOYMENT_NAME=...

"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder
from dotenv import load_dotenv

load_dotenv()


def _build_client() -> AIProjectClient:
    """Create an AIProjectClient using environment configuration."""
    try:
        endpoint = os.environ["PROJECT_ENDPOINT"]
    except KeyError as exc:
        raise RuntimeError("PROJECT_ENDPOINT environment variable is required") from exc

    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete threads whose latest message is older than a cutoff date.")
    parser.add_argument(
        "--before-date",
        dest="before_date",
        help="ISO-8601 timestamp; threads with latest messages before this moment are deleted.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days before now to use when --before-date is not provided.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Enumerate candidate threads but do not delete them.",
    )
    return parser.parse_args(argv)


def _resolve_cutoff(before_date: Optional[str], days: int) -> datetime:
    if before_date:
        try:
            parsed = datetime.fromisoformat(before_date)
        except ValueError as exc:
            raise ValueError(
                "Invalid --before-date value. Expect ISO-8601 format such as 2024-05-01 or 2024-05-01T12:34:56"
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed

    return datetime.now(timezone.utc) - timedelta(days=days)


def _normalize_datetime(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed

    return None


def _latest_message_timestamp(agents_client, thread_id: str) -> Optional[datetime]:
    try:
        messages = agents_client.messages.list(thread_id=thread_id, order=ListSortOrder.DESCENDING)
    except HttpResponseError as exc:
        print(f"  Unable to enumerate messages for thread {thread_id}: {exc}")
        return None

    iterator = iter(messages)
    while True:
        try:
            message = next(iterator)
        except StopIteration:
            break
        except ResourceNotFoundError as exc:
            print(f"  Skipping message in thread {thread_id}: {exc}")
            continue
        except HttpResponseError as exc:
            print(f"  Failed to fetch next message for thread {thread_id}: {exc}")
            break

        for attr in (
            "created_at",
            "created_on",
            "created_datetime",
            "modified_at",
            "updated_at",
            "last_modified",
            "timestamp",
        ):
            timestamp = _normalize_datetime(getattr(message, attr, None))
            if timestamp:
                return timestamp
        # Fall back to checking the message metadata dictionary when available.
        metadata = getattr(message, "metadata", None)
        if isinstance(metadata, dict):
            for key in ("created_at", "created_on", "timestamp"):
                timestamp = _normalize_datetime(metadata.get(key))
                if timestamp:
                    return timestamp

    return None


def _delete_thread(agents_client, thread_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  Dry run: thread {thread_id} would be deleted")
        return

    try:
        result = agents_client.threads.delete(thread_id=thread_id)
    except HttpResponseError as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            print(f"  Thread {thread_id} already deleted or missing; skipping")
            return
        raise

    print(f"  delete() returned: {result}")


def _iter_threads(agents_client) -> Iterable:
    try:
        pager = agents_client.threads.list()
    except HttpResponseError as exc:
        print(f"Failed to list threads: {exc}")
        return

    iterator = iter(pager)
    while True:
        try:
            thread = next(iterator)
        except StopIteration:
            break
        except ResourceNotFoundError as exc:
            print(f"Skipping thread due to API error: {exc}")
            continue
        except HttpResponseError as exc:
            print(f"Failed to fetch next thread page: {exc}")
            break
        yield thread


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)

    try:
        cutoff = _resolve_cutoff(args.before_date, args.days)
    except ValueError as exc:
        print(exc)
        return 1

    print(f"Deleting threads whose latest message is before {cutoff.isoformat()}")

    client = _build_client()
    with client:
        agents_client = client.agents

        threads_to_delete = []

        for thread in _iter_threads(agents_client):
            thread_id = getattr(thread, "id", None)
            if not thread_id:
                continue

            latest_timestamp = _latest_message_timestamp(agents_client, thread_id=thread_id)

            if latest_timestamp is None or latest_timestamp < cutoff:
                threads_to_delete.append((thread_id, latest_timestamp))

        for thread_id, latest_timestamp in threads_to_delete:
            if latest_timestamp is None:
                print(f"Deleting thread {thread_id}: no messages or timestamp available")
            else:
                print(
                    f"Deleting thread {thread_id}: latest message at {latest_timestamp.isoformat()} is before cutoff"
                )

            try:
                _delete_thread(agents_client, thread_id=thread_id, dry_run=args.dry_run)
            except HttpResponseError as exc:
                print(f"  Failed to delete thread {thread_id}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
