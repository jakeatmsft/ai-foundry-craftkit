from __future__ import annotations

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from dotenv import load_dotenv

load_dotenv()

if TYPE_CHECKING:
    from openai import OpenAI
    from openai.types.responses.response import Response

MAX_BLOCKED_DOMAIN_COUNT = 100
ABOVE_LIMIT_BLOCKED_DOMAIN_COUNT = 200


def _azure_openai_settings() -> tuple[str, str]:
    base_url = (
        os.getenv("AZURE_OPENAI_BASE_URL")
        or os.getenv("AZURE_OPENAI_API_BASE")
        or os.getenv("AZURE_OPENAI_ENDPOINT")
        or os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
    )
    model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if not base_url or not model:
        pytest.skip(
            "Set an Azure OpenAI base URL and model/deployment in .env to run "
            "this integration test."
        )

    base_url = base_url.rstrip("/")
    if not base_url.endswith("/openai/v1"):
        base_url = f"{base_url}/openai/v1"

    return base_url, model


@pytest.fixture(scope="module")
def azure_openai_client() -> Iterator[tuple[OpenAI, str]]:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    base_url, model = _azure_openai_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    with OpenAI(api_key=token_provider, base_url=base_url) as client:
        yield client, model


def _blocked_domains(count: int) -> list[str]:
    return [f"blocked-domain-{index:03d}.example" for index in range(count)]


def _run_web_search(
    client_and_model: tuple[OpenAI, str], blocked_domains: list[str]
) -> Response:
    client, model = client_and_model
    return client.responses.create(
        model=model,
        input="Search the web for current OpenAI news.",
        tools=[
            {
                "type": "web_search",
                "filters": {"blocked_domains": blocked_domains},
            }
        ],
        tool_choice="required",
    )


def test_web_search_accepts_100_blocked_domains(
    azure_openai_client: tuple[OpenAI, str],
) -> None:
    """Verify that a web search accepts the maximum of 100 blocked domains."""
    blocked_domains = _blocked_domains(MAX_BLOCKED_DOMAIN_COUNT)

    assert len(blocked_domains) == MAX_BLOCKED_DOMAIN_COUNT

    response = _run_web_search(azure_openai_client, blocked_domains)

    assert response.status == "completed"
    assert any(item.type == "web_search_call" for item in response.output)


def test_web_search_rejects_200_blocked_domains(
    azure_openai_client: tuple[OpenAI, str],
) -> None:
    """Verify that a web search rejects 200 blocked domains with HTTP 400."""
    from openai import BadRequestError

    blocked_domains = _blocked_domains(ABOVE_LIMIT_BLOCKED_DOMAIN_COUNT)

    assert len(blocked_domains) == ABOVE_LIMIT_BLOCKED_DOMAIN_COUNT

    with pytest.raises(BadRequestError) as error:
        _run_web_search(azure_openai_client, blocked_domains)

    assert error.value.status_code == 400
    error_details = str(error.value.body or error.value)
    assert "blocked_domains" in error_details
    assert str(MAX_BLOCKED_DOMAIN_COUNT) in error_details
    assert str(ABOVE_LIMIT_BLOCKED_DOMAIN_COUNT) in error_details
