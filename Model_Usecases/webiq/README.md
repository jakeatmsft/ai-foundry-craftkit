# WebIQ smoke test

Create a virtual environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template and add your Microsoft Entra credentials and
WebIQ client AppID:

```bash
cp .env.example .env
```

Configure these values in `.env`:

- `AZURE_TENANT_ID`: the Entra Directory (tenant) ID
- `AZURE_CLIENT_ID`: the Entra Application (client) ID
- `AZURE_CLIENT_SECRET`: a client secret created for the Entra app registration
- `WEBIQ_CLIENT_APP_ID`: the AppID sent in WebIQ's `oboappid` query parameter
- `WEBIQ_API_KEY`: optional API key; when set, it is preferred over Entra auth

The program sends `WEBIQ_API_KEY` in the `X-APIKey` header when it is configured.
Otherwise, it acquires an Entra bearer token for
`https://api.microsoft.ai/.default`. Both methods pass the WebIQ client AppID in
the request URL:

```text
https://api.microsoft.ai/v3/search/web?oboappid=<WEBIQ_CLIENT_APP_ID>
```

Run the test:

```bash
python webiq_test.py
```

The script sends a search for `Latest AI trends` and prints the JSON response.

## Run all CSV queries

Run every value in the `prompt` column of `websearch_results (version 1).csv`:

```bash
python batch_webiq.py
```

Select an authentication method explicitly when needed:

```bash
python batch_webiq.py --auth api-key
python batch_webiq.py --auth entra
```

The default, `--auth auto`, uses `WEBIQ_API_KEY` when configured and falls back
to Entra authentication otherwise.

Results are written incrementally to `webiq_batch_results.jsonl`. Each line has
the source CSV row, query, status, and either the WebIQ response or error details.
Duplicate queries are processed because each CSV row is treated separately.

If a run is interrupted, continue without repeating recorded rows:

```bash
python batch_webiq.py --resume
```

Use `python batch_webiq.py --help` to set a different input, output, query
column, or delay between requests.
