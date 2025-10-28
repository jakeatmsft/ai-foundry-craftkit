# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------
"""Find Azure AI agents by name, returning newest matches first."""

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


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sort_key(item: tuple) -> datetime:
    _, created_at = item
    if created_at is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return created_at


def _collect_agents_by_name(agents_client, name: str) -> list:
    matches = []
    for agent in agents_client.list_agents():
        if getattr(agent, "name", None) != name:
            continue
        created_at = _normalize_datetime(getattr(agent, "created_at", None))
        matches.append((agent, created_at))
    return sorted(matches, key=_sort_key, reverse=True)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find agents with an exact name match.")
    parser.add_argument(
        "name",
        help="Agent name to search for (case-sensitive).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    target_name = args.name

    client = _build_client()
    with client:
        agents_client = client.agents

        try:
            matches = _collect_agents_by_name(agents_client, name=target_name)
        except HttpResponseError as exc:
            print(f"Failed to enumerate agents: {exc}")
            return 1

    if not matches:
        print(f"No agents found with name '{target_name}'")
        return 0

    print(f"Agents named '{target_name}' (newest first):")
    for index, (agent, created_at) in enumerate(matches, start=1):
        created_text = created_at.isoformat() if created_at else "<unknown>"
        marker = " <- latest" if index == 1 else ""
        print(f" {index}. id: {agent.id}, created_at: {created_text}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
