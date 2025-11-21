# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""Utilities for deleting Azure AI agents.

Usage:
    python agent_cleanup.py [--agent-id <id>] [--dry-run] [--silent]

    The script connects to the Azure AI Project identified by the environment
    variables `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME`. When no `--agent-id`
    argument is provided, every agent in the project will be deleted.

Set up:
    pip install azure-ai-projects azure-ai-agents azure-identity
    export PROJECT_ENDPOINT=...
    export MODEL_DEPLOYMENT_NAME=...

"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

from azure.ai.projects import AIProjectClient
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


def delete_agent_hierarchy(agents_client, agent_id: str, dry_run: bool) -> None:
    print(f"\nDeleting resources for agent {agent_id}")

    if dry_run:
        print(f"Dry run complete for agent {agent_id}; agent not deleted.")
        return

    deletion_result = agents_client.delete_agent(agent_id=agent_id)
    print(f"delete_agent() returned: {deletion_result}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete Azure AI agents.")
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
    parser.add_argument(
        "--silent",
        dest="silent",
        action="store_true",
        help="Suppress confirmation prompts when deleting all agents.",
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

        if not args.agent_id and agent_ids:
            resource = os.environ.get("PROJECT_ENDPOINT", "configured project endpoint")
            print(
                f"WARNING: No --agent-id provided. All agents will be deleted for resource '{resource}'."
            )
            if args.dry_run:
                print("Dry run enabled: delete() calls will be skipped.")
            if not args.silent:
                confirm = input("Proceed with deleting all agents? [y/N]: ").strip().lower()
                if confirm not in {"y", "yes"}:
                    print("Operation cancelled by user.")
                    return 0

        for agent_id in agent_ids:
            try:
                delete_agent_hierarchy(agents_client, agent_id=agent_id, dry_run=args.dry_run)
            except HttpResponseError as exc:
                print(f"Failed to delete agent {agent_id}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
