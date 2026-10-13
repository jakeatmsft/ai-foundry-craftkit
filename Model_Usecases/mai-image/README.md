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
