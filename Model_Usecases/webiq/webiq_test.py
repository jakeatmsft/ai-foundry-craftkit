"""Minimal WebIQ web-search smoke test."""

# ruff: noqa: I001

from dotenv import load_dotenv

load_dotenv(override=True)  # Load .env file if present, override existing env vars

import json
import os

import msal
import requests


WEBIQ_SEARCH_URL = "https://api.microsoft.ai/v3/search/web"
WEBIQ_SCOPE = "https://api.microsoft.ai/.default"
AUTH_METHODS = {"auto", "api-key", "entra"}


def _required_environment_value(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and configure it."
        )
    return value


def acquire_entra_token() -> str:
    """Acquire an app-only WebIQ token with the client credentials grant."""
    tenant_id = _required_environment_value("AZURE_TENANT_ID")
    client_id = _required_environment_value("AZURE_CLIENT_ID")
    client_secret = _required_environment_value("AZURE_CLIENT_SECRET")

    client = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = client.acquire_token_for_client(scopes=[WEBIQ_SCOPE])
    access_token = result.get("access_token")
    if not access_token:
        error = result.get("error", "token_acquisition_failed")
        description = result.get("error_description", "No access token returned.")
        raise RuntimeError(
            f"Microsoft Entra authentication failed: {error}: {description}"
        )
    return access_token


def resolve_auth_credentials(
    auth_method: str = "auto",
) -> tuple[str | None, str | None]:
    """Return an API key or Entra access token for the selected auth method."""
    if auth_method not in AUTH_METHODS:
        choices = ", ".join(sorted(AUTH_METHODS))
        raise ValueError(f"Unknown auth method {auth_method!r}; choose from {choices}.")

    api_key = os.getenv("WEBIQ_API_KEY")
    if auth_method == "api-key" or (auth_method == "auto" and api_key):
        return _required_environment_value("WEBIQ_API_KEY"), None

    return None, acquire_entra_token()


def search_web(
    query: str = "Latest AI trends",
    *,
    print_result: bool = True,
    session: requests.Session | None = None,
    client_app_id: str | None = None,
    access_token: str | None = None,
    api_key: str | None = None,
    auth_method: str = "auto",
) -> dict:
    """Run a WebIQ search and return the decoded JSON response."""
    app_id = client_app_id or _required_environment_value("WEBIQ_CLIENT_APP_ID")
    if api_key and access_token:
        raise ValueError("Provide either api_key or access_token, not both.")
    if not api_key and not access_token:
        api_key, access_token = resolve_auth_credentials(auth_method)

    headers = {
        "content-type": "application/json",
    }
    if api_key:
        headers["X-APIKey"] = api_key
    else:
        headers["Authorization"] = f"Bearer {access_token}"
    payload = {
        "query": query,
        "maxResults": 3,
        "language": "en",
        "region": "US",
        "contentFormat": "markdown",
        "maxLength": 1000,
        "safeSearch": "strict",
    }

    requester = session or requests
    response = requester.post(
        WEBIQ_SEARCH_URL,
        params={"oboappid": app_id},
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if print_result:
        print(json.dumps(data, indent=2))
    return data


if __name__ == "__main__":
    try:
        search_web()
    except requests.exceptions.RequestException as exc:
        print(f"WebIQ request failed: {exc}")
        raise
