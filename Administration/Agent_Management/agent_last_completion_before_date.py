# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------
"""List Azure AI agents whose most recent completed run occurred before a target date."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LastCompletion:
    """Track metadata about an agent's latest completed run."""

    timestamp: datetime
    thread_id: str
    run_id: str


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


def _latest_completed_runs_by_agent(agents_client) -> dict[str, LastCompletion]:
    """Build a map of agent_id -> latest completed run metadata."""

    latest: dict[str, LastCompletion] = {}

    try:
        threads = agents_client.threads.list(order=ListSortOrder.DESCENDING)
    except HttpResponseError as exc:
        raise RuntimeError(f"Failed to enumerate threads: {exc}") from exc

    for thread in threads:
        thread_id = getattr(thread, "id", None)
        if not thread_id:
            continue

        try:
            runs = agents_client.runs.list(
                thread_id=thread_id,
                order=ListSortOrder.DESCENDING,
            )
        except HttpResponseError as exc:
            print(f"Unable to list runs for thread {thread_id}: {exc}")
            continue

        for run in runs:
            status = getattr(run, "status", None)
            if status != "completed":
                continue

            agent_id = getattr(run, "agent_id", None) or getattr(run, "assistant_id", None)
            if not agent_id:
                continue

            completed_at = _normalize_datetime(getattr(run, "completed_at", None))
            if completed_at is None:
                continue

            existing = latest.get(agent_id)
            if existing is None or completed_at > existing.timestamp:
                run_id = getattr(run, "id", "<unknown>")
                latest[agent_id] = LastCompletion(
                    timestamp=completed_at,
                    thread_id=thread_id,
                    run_id=run_id,
                )
            # runs are returned newest-first; the first completed run with metadata is the latest completion
            break

    return latest


def _collect_agents_before(agents_client, cutoff: datetime) -> list:
    """Return agents whose last completion is older than the cutoff."""

    latest_run_by_agent = _latest_completed_runs_by_agent(agents_client)

    matches = []
    try:
        agents = list(agents_client.list_agents())
    except HttpResponseError as exc:
        raise RuntimeError(f"Failed to enumerate agents: {exc}") from exc

    for agent in agents:
        info = latest_run_by_agent.get(agent.id)
        if info is None:
            continue
        if info.timestamp < cutoff:
            matches.append((agent, info))

    return sorted(matches, key=lambda item: item[1].timestamp)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List agents whose most recent completed run occurred before the provided ISO date or datetime.",
    )
    parser.add_argument(
        "cutoff",
        type=_parse_iso_datetime,
        help="Agents with a latest completed run earlier than this ISO-8601 date or datetime (UTC assumed when tz missing).",
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
        except RuntimeError as exc:
            print(str(exc))
            return 1

    if not matches:
        print(f"No agents have a completed run before {cutoff.isoformat()}")
        return 0

    print(f"Agents with latest completed run before {cutoff.isoformat()} (UTC):")
    json_output = [
        {
            "id": agent.id,
            "name": getattr(agent, "name", "<unnamed>"),
            "last_completed_at": info.timestamp.isoformat(),
            "thread_id": info.thread_id,
            "run_id": info.run_id,
        }
        for agent, info in matches
    ]
    print(json.dumps(json_output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
