# Azure Foundry Batch Job Monitor

These examples list all Azure OpenAI Batch API jobs, log their current status,
and request cancellation for active jobs older than 24 hours. Job age is
measured from `created_at`. Active statuses are `validating`, `in_progress`,
and `finalizing`; terminal or already-cancelling jobs are not changed.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt (optional)
cp .env.example .env
```

Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` in `.env`. The endpoint
may be either the resource root or the full `/openai/v1` API base.

## OpenAI SDK example

This version uses the `openai` package. SDK iteration automatically follows
pagination from `client.batches.list()`.

Preview what would be cancelled:

```bash
python monitor_batch_jobs_openai.py --dry-run
```

Perform one scan and cancel overdue jobs:

```bash
python monitor_batch_jobs_openai.py
```

Keep polling every five minutes:

```bash
python monitor_batch_jobs_openai.py --watch
```

## REST example

The dependency-light version calls the Azure OpenAI v1 endpoints directly:

```bash
python monitor_batch_jobs_REST.py --dry-run
python monitor_batch_jobs_REST.py --watch
```

Use `--max-age-hours` and `--poll-seconds` to override the `.env` defaults.
For production, run the one-shot command from a scheduler and store the API key
in Azure Key Vault rather than a plaintext `.env` file.

`ruff`, `black`, and `mypy` can be added if this utility grows beyond the POC.
