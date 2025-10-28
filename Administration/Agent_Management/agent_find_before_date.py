# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------
"""List Azure AI agents created before a user-specified date."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Iterable, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv
import json

load_dotenv()


def _env_var(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as exc:
        raise RuntimeError(f"{name} environment variable is required") from exc


def _build_client() -> AIProjectClient:
    endpoint = _env_var("PROJECT_ENDPOINT")
    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime string, defaulting to UTC when timezone is absent."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date value '{value}': {exc}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _collect_agents_before(agents_client, cutoff: datetime) -> list:
    matches = []
    for agent in agents_client.list_agents():
        created_at = _normalize_datetime(getattr(agent, "created_at", None))
        if created_at is None:
            continue
        if created_at < cutoff:
            matches.append((agent, created_at))
    return matches


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List agents created before the provided ISO date or datetime."
    )
    parser.add_argument(
        "cutoff",
        type=_parse_iso_datetime,
        help="Agents with created_at earlier than this ISO-8601 date or datetime (UTC assumed when tz missing).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    cutoff = args.cutoff

    client = _build_client()
    with client:
        agents_client = client.agents

        try:
            matches = _collect_agents_before(agents_client, cutoff=cutoff)
        except HttpResponseError as exc:
            print(f"Failed to enumerate agents: {exc}")
            return 1

    if not matches:
        print(f"No agents were created before {cutoff.isoformat()}")
        return 0

    print(f"Agents created before {cutoff.isoformat()} (UTC):")
    # print a json list sorted by creation time
    json_output = [{"id": agent.id, "name": agent.name, "created_at": created_at.isoformat()} for agent, created_at in sorted(matches, key=lambda item: item[1])]
    print(json.dumps(json_output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
