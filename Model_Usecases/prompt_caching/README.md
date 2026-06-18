# Prompt Caching Test

Simple Azure OpenAI prompt caching test script.

The script:
- Sends 5 chat completion requests in a row.
- Keeps the long prompt prefix identical across requests.
- Changes the question on each run.
- Prints a table for each request and a final summary table.

## Files

- `prompt_cache_test.py`: runs the prompt caching test
- `.env`: local configuration

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install openai azure-identity python-dotenv
```

Sign in for Azure auth:

```bash
az login
```

## Configuration

Set values in `.env`:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-5
PROMPT_CACHE_RETENTION=24h
AZURE_OPENAI_API_KEY=
```

Notes:
- If `AZURE_OPENAI_API_KEY` is empty, the script uses Azure Entra auth via `DefaultAzureCredential`.
- If `AZURE_OPENAI_API_KEY` is set, the script uses API key auth instead.
- `PROMPT_CACHE_RETENTION` is optional. Leave it blank if you want the model default.

## Run

```bash
python prompt_cache_test.py
```

## Output

The script prints:
- A request table with `latency`, `prompt_tokens`, `cached_tokens`, `completion_tokens`, and `total_tokens`
- A summary table with totals across all 5 calls

Prompt caching is working when later requests show `cached_tokens > 0`.
