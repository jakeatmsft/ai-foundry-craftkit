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
