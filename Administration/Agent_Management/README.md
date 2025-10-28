# Agent Management Utilities

Utilities for creating and cleaning up Azure AI Foundry agents during testing.

## Prerequisites
- Python 3.9+
- Packages: `azure-ai-projects`, `azure-ai-agents`, `azure-identity`
- Azure credentials supported by `DefaultAzureCredential`

Install dependencies:

```bash
pip install azure-ai-projects azure-ai-agents azure-identity
```

## Configuration
Edit `sample.env` with your project information, then load it before running the scripts:

```bash
source sample.env
```

Required variables:
- `PROJECT_ENDPOINT`
- `MODEL_DEPLOYMENT_NAME`

Optional (for service principal auth):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

## Create Test Data
Use `agent_setup.py` to create a test agent with threads and messages:

```bash
python agent_setup.py --thread-count 3 --message-template "Thread {index} hello!"
```

Key arguments:
- `--agent-name`: friendly name for the agent (default `cleanup-test-agent`).
- `--instructions`: instructions supplied when creating the agent.
- `--thread-count`: number of threads to create.
- `--message-template`: text for the user message; `{index}` is replaced per thread.
- `--poll-interval`: seconds between run status checks (default `1.0`).

## Find Agents by Creation Date
Use `agent_find_before_date.py` to list agents created before a given ISO-8601 date or datetime:

```bash
python agent_find_before_date.py 2024-05-01
```

The cutoff is interpreted in UTC when no timezone is provided. The script prints matching agent names, IDs, and timestamps sorted by creation time, along with a total count.

## Find Agents by Name
Use `agent_find_by_name.py` to locate agents that share an exact name, with the newest creation date first:

```bash
python agent_find_by_name.py "cleanup-test-agent"
```

Results are ordered by `created_at` descending; the first entry is marked as the latest instance.

## Find Agents by Last Completion Date
Use `agent_last_completion_before_date.py` to list agents whose most recent completed run finished before an ISO-8601 date or datetime:

```bash
python agent_last_completion_before_date.py 2024-05-01T00:00:00Z
```

The script inspects every thread and run to determine the latest successful completion per agent. Results include the agent identifiers, the run timestamp, and the associated thread and run IDs to help trace the activity.

## Cleanup Agents
Run `agent_cleanup.py` to delete agents plus their threads and messages:

```bash
# Preview without deleting
python agent_cleanup.py --dry-run

# Delete everything
python agent_cleanup.py

# Target a single agent
python agent_cleanup.py --agent-id <agent_id>
```

The cleanup script lists every message and thread before calling the respective `delete()` APIs. Use the dry run mode to confirm what would be removed.

## Notes
- Both scripts rely on `DefaultAzureCredential`; ensure your environment or developer workstation is authenticated.
- The cleanup process enumerates all threads and filters them to the specified agent. This is a workaround for current SDK limitations around agent-scoped thread pagination.
