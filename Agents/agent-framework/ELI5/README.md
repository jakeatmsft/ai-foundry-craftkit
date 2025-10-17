# Agent Framework ELI5 Notebooks

This directory contains “explain like I’m five” (ELI5) notebooks that walk through the Agent Framework getting-started samples. Each notebook rebuilds a Python sample from `python/samples/getting_started/workflows/` with extra commentary so you can explore the workflow step by step without jumping between the notebook and the source file.

## Getting Started
- Set up the same Python environment used for the Agent Framework samples (follow the repository’s setup instructions for `python/samples/getting_started`).
- Launch Jupyter Lab, VS Code, or your preferred notebook environment inside that environment.
- Open any of the notebooks below and execute the cells from top to bottom. They expect the same configuration (API keys, endpoints, etc.) that the corresponding sample script requires.

## Notebook Guide

### `_start-here`
- `step1_executors_and_edges.ipynb` – Introduces the core workflow building blocks by recreating `step1_executors_and_edges.py` with inline explanations.
- `step2_agents_in_a_workflow.ipynb` – Mirrors `step2_agents_in_a_workflow.py` to show how agents plug into a workflow and communicate.
- `step3_streaming.ipynb` – Expands `step3_streaming.py`, highlighting how streaming responses move through the workflow.

### `agents`
- `azure_ai_agents_streaming.ipynb` – Walks through the Azure AI Agents streaming sample with commentary on each orchestration step.
- `azure_chat_agents_streaming.ipynb` – Recreates the Azure Chat Agents streaming workflow, calling out configuration and message flow details.
- `custom_agent_executors.ipynb` – Demonstrates how custom executors are composed inside an agent-centric workflow.
- `workflow_as_agent_human_in_the_loop.ipynb` – Shows how a workflow can surface human input opportunities while acting as an agent.
- `workflow_as_agent_reflection_pattern.ipynb` – Breaks down the reflection-pattern workflow where an agent critiques and revises its own outputs.

### `checkpoint`
- `checkpoint_with_human_in_the_loop.ipynb` – Explains the checkpoint pattern that pauses for human feedback before resuming execution.
- `checkpoint_with_resume.ipynb` – Covers the resume-from-checkpoint scenario and how state is persisted across runs.
- `sub_workflow_checkpoint.ipynb` – Details how checkpoints work inside nested sub-workflows.

### `composition`
- `sub_workflow_basics.ipynb` – Revisits the basics of composing sub-workflows inside a larger orchestration.
- `sub_workflow_parallel_requests.ipynb` – Highlights how parallel requests are fanned out and reconciled inside a sub-workflow.
- `sub_workflow_request_interception.ipynb` – Shows how to intercept and inspect requests as they travel between sub-workflows.

### `control-flow`
- `edge_condition.ipynb` – Describes how conditional edges route execution based on runtime context.

### `human-in-the-loop`
- `guessing_game_with_human_input.ipynb` – Walks through a playful human-in-the-loop sample that requests user guesses during execution.

### `parallelism`
- `aggregate_results_of_different_types.ipynb` – Explains how to aggregate heterogeneous results returned from parallel branches.
- `fan_out_fan_in_edges.ipynb` – Breaks down the fan-out/fan-in edge pattern for coordinating parallel work.
- `map_reduce_and_visualization.ipynb` – Walks through a map-reduce style workflow and highlights the visualization hooks.

Each notebook keeps the original sample code close by, making it easier to understand how the Agent Framework APIs come together in practice.
