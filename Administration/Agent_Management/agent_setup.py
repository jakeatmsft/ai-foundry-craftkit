# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

"""Utility to provision Azure AI agents populated with threads and messages.

Usage:
    python agent_setup.py [--agent-name NAME] [--thread-count N] [--message-template TEMPLATE]

The script requires the environment variables `PROJECT_ENDPOINT` and
`MODEL_DEPLOYMENT_NAME` to be set, matching the Azure AI Foundry project where
resources should be created. It creates one agent by default and populates the
requested number of threads, each seeded with a user message and an agent
response produced by running the agent.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Iterable, Optional

from azure.identity import DefaultAzureCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    AgentThreadCreationOptions,
    ListSortOrder,
    ThreadMessageOptions,
)
from dotenv import load_dotenv

load_dotenv()

POLL_STATUSES = {"queued", "in_progress", "requires_action"}


def _env_var(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as exc:
        raise RuntimeError(f"{name} environment variable is required") from exc


def _build_client() -> AIProjectClient:
    endpoint = _env_var("PROJECT_ENDPOINT")
    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def _create_agent(agents_client, name: str, instructions: str) -> str:
    model_deployment = _env_var("MODEL_DEPLOYMENT_NAME")
    agent = agents_client.create_agent(
        model=model_deployment,
        name=name,
        instructions=instructions,
    )
    print(f"Created agent '{agent.name}' with id {agent.id}")
    return agent.id


def _poll_run(agents_client, run, poll_interval: float) -> None:
    while run.status in POLL_STATUSES:
        time.sleep(poll_interval)
        run = agents_client.runs.get(thread_id=run.thread_id, run_id=run.id)
        print(f"  Run {run.id} status: {run.status}")

    if run.status == "failed":
        raise RuntimeError(f"Run {run.id} failed: {run.last_error}")


def _populate_thread(
    agents_client,
    agent_id: str,
    thread_index: int,
    turn_count: int,
    message_template: str,
    poll_interval: float,
) -> str:
    turn_count = max(1, turn_count)
    first_message = message_template.format(index=thread_index, turn=1)
    print(f" Creating thread with user message: {first_message!r}")

    run = agents_client.create_thread_and_run(
        agent_id=agent_id,
        thread=AgentThreadCreationOptions(
            messages=[ThreadMessageOptions(role="user", content=first_message)]
        ),
    )

    _poll_run(agents_client, run, poll_interval=poll_interval)

    thread_id = run.thread_id
    print(f"  Created thread {thread_id}")

    for turn in range(2, turn_count + 1):
        user_message = message_template.format(index=thread_index, turn=turn)
        print(f"  Adding turn {turn}: {user_message!r}")
        agents_client.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message,
        )

        followup_run = agents_client.runs.create(
            thread_id=thread_id,
            agent_id=agent_id,
        )
        _poll_run(agents_client, followup_run, poll_interval=poll_interval)

    return thread_id


def _show_messages(agents_client, thread_id: str) -> None:
    messages = list(agents_client.messages.list(thread_id=thread_id, order=ListSortOrder.ASCENDING))
    if not messages:
        print(f"   No messages recorded for thread {thread_id}")
        return

    print(f"   Messages for thread {thread_id}:")
    for message in messages:
        if message.text_messages:
            last_text = message.text_messages[-1]
            preview = last_text.text.value
        else:
            preview = "<non-text payload>"
        print(f"     [{message.role}] {message.id}: {preview}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create agent resources for cleanup testing.")
    parser.add_argument(
        "--agent-name",
        default="cleanup-test-agent",
        help="Name for the agent to create.",
    )
    parser.add_argument(
        "--instructions",
        default="You are a test assistant that responds cheerfully.",
        help="Instructions to supply to the agent.",
    )
    parser.add_argument(
        "--thread-count",
        type=int,
        default=1,
        help="Number of threads to create for the agent.",
    )
    parser.add_argument(
        "--message-template",
        default="Hello from test thread {index}, turn {turn}!",
        help="Template for user messages; supports {index} and {turn} placeholders.",
    )
    parser.add_argument(
        "--turn-count",
        type=int,
        default=5,
        help="Number of user/assistant turns to create for each thread (minimum 1).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between run status checks.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    client = _build_client()
    with client:
        agents_client = client.agents

        try:
            agent_id = _create_agent(agents_client, name=args.agent_name, instructions=args.instructions)
        except HttpResponseError as exc:
            print(f"Failed to create agent: {exc}")
            return 1

        for index in range(1, args.thread_count + 1):
            try:
                thread_id = _populate_thread(
                    agents_client,
                    agent_id=agent_id,
                    thread_index=index,
                    turn_count=args.turn_count,
                    message_template=args.message_template,
                    poll_interval=args.poll_interval,
                )
            except Exception as exc:  # pylint: disable=broad-except
                print(f" Failed to create thread {index}: {exc}")
                continue

            _show_messages(agents_client, thread_id=thread_id)

        print("\nSetup complete. Use agent_cleanup.py to remove these resources when finished testing.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
