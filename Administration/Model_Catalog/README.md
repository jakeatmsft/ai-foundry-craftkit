# Model catalog lookup notebook

Open [model_catalog_lookup.ipynb](output/jupyter-notebook/model_catalog_lookup.ipynb) to retrieve details for a model from <https://ai.azure.com/catalog/models/>. Nothing is published or deployed.

The notebook provides `get_model_details(name, version=None)`, returning publisher, version, tasks, token limits, modalities, deployment types, licensing, the full model card, evaluations, notes, and the original model record where supplied. It records the source URL and retrieval time. Missing fields remain `None`.

## Run

Use Python 3.10 or newer from this directory:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env      # PowerShell: Copy-Item .env.example .env
jupyter lab output/jupyter-notebook/model_catalog_lookup.ipynb
```

Select the `.venv` kernel. Set `CATALOG_MODEL_NAME` in `.env` to an exact catalog URL slug, such as `Phi-4` or `gpt-4.1`. Leave `CATALOG_MODEL_VERSION` blank for the version displayed by the catalog, or set an exact version string. Run the notebook top to bottom.

The default lookup needs internet access but no credentials. JSON export, a second lookup, and authenticated Azure examples are disabled by default. Enable their switches only when needed. JSON exports stay in the Git-ignored `output/model-details/` directory.

## Supported APIs and extraction coverage

| Source | Use it for | Requirements |
| --- | --- | --- |
| Public catalog HTML | The model card and metadata embedded in a model detail page | Anonymous HTTPS; undocumented page-data format |

The notebook includes runnable optional examples for both supported interfaces and handles REST pagination. The documented REST endpoint is:

```http
GET https://management.azure.com/subscriptions/{subscriptionId}/providers/Microsoft.CognitiveServices/locations/{location}/models?api-version=2025-06-01
Authorization: Bearer <Entra token for https://management.azure.com/>
```

The public catalog includes more presentation content than these supported APIs necessarily return. No documented anonymous API covering the complete public catalog page was identified during this investigation. The default extractor reads the structured JSON reference table embedded in the public HTML; it never executes page JavaScript. **This is an undocumented website format, not a Microsoft-supported API.** A layout/schema change produces a clear error instead of an empty result.

The extractor retrieves one model page, not a complete catalog inventory. Embedded version lists can be incomplete; check `versions_complete` or use the registry SDK. Token limits, pricing prose and other source fields can disagree; the original record is retained for inspection. Regional model lists do not establish subscription quota or deployment capacity, and registry replication locations are not presented as deployment availability.

## Configuration

`.env` is loaded before clients are created. See [.env.example](.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `CATALOG_MODEL_NAME` | `Phi-4` | Exact public catalog URL slug |
| `CATALOG_MODEL_VERSION` | Empty | Exact version, or the catalog default |
| `AZURE_SUBSCRIPTION_ID` | Empty | Optional regional REST request |
| `AZURE_LOCATION` | `eastus` | Optional regional REST request |
| `AZURE_MODELS_API_VERSION` | `2025-06-01` | Supported regional REST API version |

For authenticated examples, install `azure-identity azure-ai-ml` and run `az login`, or use managed identity in Azure. Service principals can use `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` in `.env`. Do not put credentials into notebook cells or outputs. No inference API key is required.

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check tests output/jupyter-notebook/model_catalog_lookup.ipynb
python -m black --check tests output/jupyter-notebook/model_catalog_lookup.ipynb
```

Tests load the notebook's definition cells and exercise the actual lookup functions offline: version selection, missing values, malformed page data, HTTP failures, and ARM pagination. Ruff, Black, and mypy configuration is supplied in `pyproject.toml`; mypy can check Python exported from the notebook.

All 12 code cells executed top to bottom, and all 25 offline tests passed. Live public lookups for **Phi-4** and **gpt-4.1** succeeded on **2026-10-05**. Authenticated SDK/REST integration testing remains a follow-up for an Azure environment with the appropriate access. No cloud resources were created.

This task uses direct HTTP/SDK calls and has no agent orchestration. If developed into a service later, add caching, rate limits, authentication, schema-change monitoring, Azure Monitor/Application Insights, and CI integration checks. Use managed identity/Key Vault for future secrets and plan networking and scaling when there is a deployment target.
