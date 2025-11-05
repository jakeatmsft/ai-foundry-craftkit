# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""Utilities for deleting Azure AI agents together with their threads and messages.

Usage:
    python agent_cleanup.py [--agent-id <id>] [--dry-run]

    The script connects to the Azure AI Project identified by the environment
    variables `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME`. When no `--agent-id`
    argument is provided, every agent in the project will be deleted. Threads are
    discovered via the runs created for each agent.

Set up:
    pip install azure-ai-projects azure-ai-agents azure-identity
    export PROJECT_ENDPOINT=...
    export MODEL_DEPLOYMENT_NAME=...

"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional, Sequence

from azure.core.exceptions import HttpResponseError
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


def _gather_agent_ids(agents_client, target_agent_id: Optional[str]) -> Iterable[str]:
    if target_agent_id:
        yield target_agent_id
        return

    for agent in agents_client.list_agents():
        yield agent.id


def _collect_thread_ids(agents_client, agent_id: str) -> Sequence[str]:
    """Return all thread identifiers that have runs associated with the agent."""

    thread_ids = []
    seen = set()

    try:
        threads = agents_client.threads.list()
    except HttpResponseError as exc:
        print(f"Failed to list threads: {exc}")
        return thread_ids

    for thread in threads:
        thread_id = getattr(thread, "id", None)
        if not thread_id or thread_id in seen:
            continue
        seen.add(thread_id)

        thread_agent_id = getattr(thread, "agent_id", None)
        if thread_agent_id == agent_id:
            thread_ids.append(thread_id)
            continue

        if _thread_has_agent_run(agents_client, thread_id=thread_id, agent_id=agent_id):
            thread_ids.append(thread_id)

    return thread_ids


def _thread_has_agent_run(agents_client, thread_id: str, agent_id: str) -> bool:
    try:
        runs = agents_client.runs.list(thread_id=thread_id)
    except HttpResponseError as exc:
        print(f"  Unable to enumerate runs for thread {thread_id}: {exc}")
        return False

    for run in runs:
        if getattr(run, "agent_id", None) == agent_id:
            return True

    return False


def _delete_messages(agents_client, thread_id: str, dry_run: bool) -> None:
    messages = list(agents_client.messages.list(thread_id=thread_id, order=ListSortOrder.ASCENDING))
    if not messages:
        print(f"  No messages found for thread {thread_id}")
        return

    for message in messages:
        print(f"  Deleting message {message.id} from thread {thread_id} ({message.role})")
        if dry_run:
            continue

        try:
            deletion_result = agents_client.messages.delete(thread_id=thread_id, message_id=message.id)
        except HttpResponseError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 404 or "No enterprise message found" in str(exc):
                print(f"    Message {message.id} already deleted or missing; skipping ({exc})")
                continue
            raise

        print(f"    delete() returned: {deletion_result}")


def _delete_threads(agents_client, agent_id: str, dry_run: bool) -> None:
    thread_ids = _collect_thread_ids(agents_client, agent_id=agent_id)
    if not thread_ids:
        print(f"No threads found for agent {agent_id}")
        return

    for thread_id in thread_ids:
        print(f"Processing thread {thread_id} for agent {agent_id}")
        _delete_messages(agents_client, thread_id, dry_run=dry_run)

        if dry_run:
            continue

        deletion_result = agents_client.threads.delete(thread_id=thread_id)
        print(f"  delete() returned: {deletion_result}")


def delete_agent_hierarchy(agents_client, agent_id: str, dry_run: bool) -> None:
    print(f"\nDeleting resources for agent {agent_id}")

    _delete_threads(agents_client, agent_id=agent_id, dry_run=dry_run)

    if dry_run:
        print(f"Dry run complete for agent {agent_id}; agent not deleted.")
        return

    deletion_result = agents_client.delete_agent(agent_id=agent_id)
    print(f"delete_agent() returned: {deletion_result}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete Azure AI agents with associated threads and messages.")
    parser.add_argument(
        "--agent-id",
        dest="agent_id",
        help="Only delete the agent with this identifier. Defaults to deleting all agents.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Enumerate resources but do not call delete().",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    client = _build_client()
    with client:
        agents_client = client.agents

        agent_ids = list(_gather_agent_ids(agents_client, args.agent_id))
        if not agent_ids:
            print("No agents found to delete.")
            return 0

        for agent_id in agent_ids:
            try:
                delete_agent_hierarchy(agents_client, agent_id=agent_id, dry_run=args.dry_run)
            except HttpResponseError as exc:
                print(f"Failed to delete agent {agent_id}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
