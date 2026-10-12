# MAI image generation with Azure credentials

Run [generate_images_azure_identity.ipynb](generate_images_azure_identity.ipynb) to
generate, save, and display a PNG using a deployed MAI image model and Microsoft
Entra ID authentication. The request follows the
[MAI image API documentation](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image?tabs=python#api-endpoints).

## Setup and run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install requests azure-identity python-dotenv jupyterlab
cp .env.example .env
az login
jupyter lab generate_images_azure_identity.ipynb
```

Edit `.env` with your resource and deployment before running all cells in order.
Select the kernel from this virtual environment. Your identity needs inference
permissions on the resource. Managed identity can replace `az login` in Azure.

| Variable | Value |
| --- | --- |
| `AZURE_ENDPOINT` | Required resource root, such as `https://contoso.services.ai.azure.com`; omit project and API paths. |
| `DEPLOYMENT_NAME` | Required exact name of your deployed MAI image model. |
| `IMAGE_PROMPT` | Optional description; defaults to a mountain lake at sunrise. |
| `IMAGE_WIDTH`, `IMAGE_HEIGHT` | Default to `1024`; each must be at least `768`, with a product no greater than `1,048,576`. |
| `OUTPUT_PATH` | Defaults to `output.png`; each save adds a timestamp and uses a `.png` extension. |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Optional service principal credentials for `DefaultAzureCredential`. |

Rerun setup after editing `.env`; its values take precedence over existing
environment values. The request cell asks the token provider for a valid token on
every run and includes the service error details when a request fails.

## Validation

Check notebook structure without making an API request:

```bash
python -c "import nbformat; nbformat.validate(nbformat.read('generate_images_azure_identity.ipynb', as_version=4))"
```

For a live smoke test, restart the kernel and run all cells. Expect a saved PNG
and an inline image. Live integration tests are not automated; they require a
deployment, credentials, and quota and incur image-generation usage charges.

## GPT + MAI showcase: six models, three Azure resources

Open [gpt_image_azure_showcase.ipynb](output/jupyter-notebook/gpt_image_azure_showcase.ipynb)
for product photography, exact-text posters, illustrations, portrait transformations,
and transparent mascot requests. The same prompt is used across all six models; edits
use identical bytes from the supplied [reference portrait](assets/reference_portrait.png).

The [saved comparison gallery](output/jupyter-notebook/comparisons/index.html) includes
all five prompts, with **API differences and pricing tables below the images**. Saved GPT
images use `low` quality and 1024×1024 output. MAI uses model-default quality, 1024×1024
for generation, and no explicit dimensions for edits. Captions show actual dimensions.
Different provider defaults are not an equal-quality benchmark.

| Models | Resource endpoint |
| --- | --- |
| `gpt-image-1.5`, `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst` | `https://aikb-openai-dkds4s3eonm5o.openai.azure.com` |
| `gpt-image-2` | `https://wu3-oai.cognitiveservices.azure.com` |
| `MAI-Image-2.6`, `MAI-Image-2.6-Flash` | `https://jacwang-foundryonly.services.ai.azure.com` |

All six deployment names and versions were verified through Azure on 2026-09-14.
Both MAI deployments use model version `2026-07-31`, Global Standard, on the East US
resource `jacwang-foundryonly` in `jacwang-rg`. The clients use Microsoft Entra ID.

### MAI vs. Azure OpenAI: endpoint, payload, and usage

| Detail | GPT image models | MAI 2.6 and Flash |
| --- | --- | --- |
| Generate URL | `/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview` | `/mai/v1/images/generations` (no query version) |
| Edit URL | Same deployment prefix + `/images/edits?api-version=...` | `/mai/v1/images/edits` |
| Client | `AzureOpenAI.images.generate()` / `.edit()` | `requests.Session.post()` |
| Generation JSON | `model`, `prompt`, `n`, `size`, `quality`, `output_format`, `background` | `model`, `prompt`, `width`, `height`, `auto_aspect_ratio`, `web_grounding` |
| Edit multipart | `image` plus GPT fields | `image`, `model`, `prompt`, MAI flags; width/height omitted |
| Dimensions | Shared demo sizes: 1024×1024, 1536×1024, 1024×1536 | Each generation dimension ≥768; total ≤1,048,576 pixels. A 1536×1024 request exceeds the MAI limit. |
| Quality / alpha | Explicit quality and transparent background control | No documented quality/background fields; transparent mascot is a prompt-only test |
| Response image | `data[0].b64_json` | Same base64 field; PNG output |
| Reported usage | `input_tokens_details`, `output_tokens_details`, and totals | `num_input_text_tokens`, `num_input_image_tokens`, `num_output_tokens`; no output text/image split |
| Cost estimate | Reported modality counts × matching token rates | User-supplied MAI-Image-2 starting rates for both models: $5 text input / $33 image output per million tokens; image-input rate unspecified |

Both API families use the Entra scope `https://cognitiveservices.azure.com/.default`,
with inference permission on the corresponding resource. Both MAI models share the
same API contract; change the deployment in `model`. The notebook includes side-by-side
JSON payloads and actual response examples. `web_grounding` and `auto_aspect_ratio` are
disabled. No OpenAI-only parameters are sent to MAI.

The live MAI product response reports 97 text-input tokens, zero image-input tokens,
and 1,024 output tokens; the analysis sums them to 1,121 total tokens. It does not
invent an output modality split. GPT Image 1.5 reports 104 text-input, 127 text-output,
and 272 image-output tokens for the same prompt. Tokenization and quality differ.

Both MAI transparent mascot results were **opaque PNGs with a painted checkerboard**, not alpha transparency. All four GPT saved mascot
results contain transparent pixels. The gallery labels alpha presence explicitly;
PNG format alone does not imply transparency. See the
[Microsoft MAI API documentation](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image).

### Run the showcase

```bash
pip install -r requirements-image-showcase.txt
# For a fresh setup only; preserve your existing .env.
cp .env.example .env
az login --tenant 16b3c013-d300-468d-ac64-7eda0820b6d3
jupyter lab output/jupyter-notebook/gpt_image_azure_showcase.ipynb
```

Set the three endpoints above in `.env`; it is loaded before clients and overrides
inherited environment values. Existing `AZURE_ENDPOINT` / `DEPLOYMENT_NAME` settings
for the original MAI notebook are preserved.

| Variable | Default / purpose |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | First GPT resource; falls back to existing `AZURE_ENDPOINT`. |
| `AZURE_OPENAI_GPT_IMAGE_2_ENDPOINT` | Required separate GPT Image 2 endpoint. |
| `AZURE_MAI_ENDPOINT` | Required MAI resource root ending in `.services.ai.azure.com`. |
| `AZURE_OPENAI_API_VERSION` | `2025-04-01-preview`; used only by GPT. |
| `AZURE_OPENAI_GPT_IMAGE_2_API_VERSION` | Defaults to the first GPT API version. |
| `GPT_IMAGE_15_DEPLOYMENT`, `GPT_IMAGE_2_DEPLOYMENT`, `GPT_IMAGE_FLARE_DEPLOYMENT`, `GPT_IMAGE_SUNBURST_DEPLOYMENT` | Exact GPT deployment names from the table above. |
| `MAI_IMAGE_26_DEPLOYMENT`, `MAI_IMAGE_26_FLASH_DEPLOYMENT` | `MAI-Image-2.6`, `MAI-Image-2.6-Flash`. |
| `GPT_IMAGE_QUALITY` | `medium`; GPT-only shared choices: low, medium, high, auto. |
| `GPT_IMAGE_SIZE` | `1024x1024`; GPT-only. |
| `MAI_IMAGE_WIDTH`, `MAI_IMAGE_HEIGHT` | Both `1024`; MAI generation only. |
| `MAI_IMAGE_MIN_INTERVAL_SECONDS` | `30` between starts per MAI model; increase for your quota. |
| `GPT_IMAGE_OUTPUT_DIR` | `outputs/gpt-image-showcase`, relative to this project. |

Run cells in order. The default makes **30 requests**: 18 generations, six portrait
edits, and six transparent mascot attempts. To run six requests, set
`SELECTED_SCENARIOS = ["product"]`, `RUN_EDITS = False`, and `RUN_TRANSPARENCY = False`.
The optional Flare quality sweep adds four requests: low, medium, high, and xhigh; MAI has no quality control.
Each call saves a new PNG and JSON record. Failed requests retain status, error, and
request ID without stale images. Automatic retries are disabled; inspect rate-limit
errors and retry intervals before rerunning. Live requests incur Azure usage charges.

### Token usage and cost comparison

Open [gpt_image_token_cost_comparison.ipynb](output/jupyter-notebook/gpt_image_token_cost_comparison.ipynb)
or the [interactive cost dashboard](output/jupyter-notebook/cost-analysis/index.html).
The notebook runs offline from saved response records and exports CSV/JSON provenance.
All six models appear in the request audit and reported-token totals. The matched GPT
modality/cost comparison retains the four models with identical prompt/settings and
complete modality usage. MAI totals are shown separately at model-default settings.

The default GPT prices are **public OpenAI list prices with uncached inputs**, retrieved
2026-09-14; MAI uses the user-supplied starting-rate assumption. They are reference estimates, not verified Azure prices or an invoice.
MAI estimates use the user-supplied MAI-Image-2 starting rates for both models: **$5 per
million text-input tokens and $33 per million image-output tokens**. For pricing, the
MAI output total is treated as image output under an explicit assumption in the rate
file; raw output modality counts remain unavailable. Image-input pricing was not supplied,
so portrait edits show a known text/output subtotal and an unavailable full cost. Pixels are not tokens. The user-supplied Apidog quality-price table remains
in the gallery, with its unspecified model/pricing basis noted; it is not applied to MAI.

```bash
pip install -r requirements-image-costs.txt
jupyter lab output/jupyter-notebook/gpt_image_token_cost_comparison.ipynb
```

| Optional variable | Default / purpose |
| --- | --- |
| `GPT_IMAGE_COST_INPUT` | `output/jupyter-notebook/comparisons`; also accepts a run directory or manifest. |
| `GPT_IMAGE_PRICING_FILE` | `assets/gpt_image_reference_rates.json`; override with your Azure rate file. |
| `GPT_IMAGE_COST_VOLUME` | `1000` projected images using the matched GPT prompt mix. |
| `GPT_IMAGE_COST_OUTPUT_DIR` | `output/jupyter-notebook/cost-analysis`. |

Copy [azure_image_rates.example.json](assets/azure_image_rates.example.json) for your
Azure **per-million-token** rates. Match region, model, and deployment type. Do not put
per-image prices into token-rate columns. The templates prefill the supplied MAI text-input and image-output rates. Leave image-input
rates null until supplied; positive image-input tokens prevent complete edit/workload
totals. `mai_output_tokens_as_image_output=true` records the pricing assumption. No cache, tax, or negotiated discount is inferred.

GPT repeats are averaged within a matched prompt/settings group before groups are
weighted equally. Missing prices prevent complete workload totals. The separate
all-model observed-token table averages successful saved requests, so its latency and
token values describe these samples, not a controlled performance benchmark.

### Validation

```bash
pip install pytest ruff
pytest -q tests/test_gpt_image_showcase.py tests/test_gpt_image_costs.py
ruff check output/jupyter-notebook/*.ipynb tests/test_gpt_image*.py
```

Offline checks exercise real OpenAI and requests serialization with mocked HTTP,
including all three resources, JSON/multipart fields, MAI size limits, failure recording,
usage normalization, missing values, cost arithmetic, repeated prompts, and matched
cohorts. The analysis notebook is executed against the saved dataset. Live results
establish the observed capability differences; one sample per prompt/model does not
establish a general speed or quality ranking. For production, add bounded transient
retries, telemetry, storage retention, and CI checks. Ruff is configured locally;
broader Black/mypy adoption remains a follow-up.

MAI generation estimates under the supplied starting rates are identical for both
models in these saved samples: product **$0.034277**, poster **$0.034367**, illustration
**$0.034282**, and mascot **$0.034117**. The four priced prompts average **$0.03426075**.
Each portrait has a **$0.034374 known subtotal plus unpriced image-input usage** (233 tokens).
The all-model summary labels priced-prompt averages separately from full-workload costs;
four of five MAI prompts are fully priced. Pricing tables remain below the gallery images.

The comparison gallery now includes seven interactive charts for token composition,
latency, token rates, supplied quality prices, average priced prompts, workload
projections, and per-prompt costs. Hover for exact values or use a chart's camera icon
to download a PNG. The local `comparisons/plotly.min.js` bundle keeps charts available
offline. Keep it beside `index.html` when copying the gallery.

After recalculating the cost notebook, refresh the gallery charts from its exported
CSV/JSON files and the existing Apidog table:

```bash
python scripts/render_comparison_charts.py
```

The renderer preserves existing images, comparison text, and tables. MAI portrait
heatmap cells remain uncolored because their complete cost is unavailable; the known
text/output subtotal is labeled separately.

### Flare quality comparison: low through xhigh

The gallery's **GPT Image 2.5 Flare: low → xhigh** section compares four fresh ORBIT
product images at `low`, `medium`, `high`, and `xhigh`, all using 1024×1024 PNG output.
It includes the images, request metadata, measured tokens, reference total costs, and
cost/latency graphs. These additional samples are stored under
`comparisons/flare-quality/` and are excluded from the six-model baseline averages.

To run a new sweep, set `RUN_QUALITY_SWEEP=True` in the showcase notebook. It adds four
requests, paced at least 35 seconds apart by default. The extended quality levels apply
to the deployed `gpt-image-2.5-flare`; shared six-model defaults remain unchanged.
To rebuild the saved section and graphs without generating images:

```bash
python scripts/render_flare_quality_comparison.py
python scripts/render_comparison_charts.py
```
