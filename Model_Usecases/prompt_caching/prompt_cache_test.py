#!/usr/bin/env python3
from __future__ import annotations

import os
import time

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI

RUN_COUNT = 5
QUESTION_TEMPLATE = "Answer in five words or fewer: what run number is this? Run {run_number}."


def build_client() -> tuple[OpenAI, str, str]:
    load_dotenv()

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("AZURE_OPENAI_MODEL")

    if not endpoint:
        raise ValueError("Missing AZURE_OPENAI_ENDPOINT in .env")
    if not model:
        raise ValueError("Missing AZURE_OPENAI_DEPLOYMENT or AZURE_OPENAI_MODEL in .env")

    base_url = endpoint.rstrip("/")
    if not base_url.endswith("/openai/v1"):
        base_url = f"{base_url}/openai/v1"

    if api_key:
        return OpenAI(api_key=api_key, base_url=base_url), model, "api_key"

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return OpenAI(api_key=token_provider, base_url=base_url), model, "azure_auth"


def long_prefix() -> str:
    line = (
        "Prompt caching test. Keep this prefix identical across requests. "
        "This text exists only to create a long shared prefix for caching.\n"
    )
    return line * 250


def run_request(client: OpenAI, model: str, question: str) -> tuple[float, int, int]:
    extra_body = {"prompt_cache_key": "simple-prompt-cache-demo"}
    retention = os.getenv("PROMPT_CACHE_RETENTION")
    if retention:
        extra_body["prompt_cache_retention"] = retention

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": long_prefix()},
            {"role": "user", "content": question},
        ],
        extra_body=extra_body,
    )
    elapsed = time.perf_counter() - start

    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0

    return elapsed, prompt_tokens, cached_tokens


def main() -> None:
    client, model, auth_mode = build_client()

    print(f"Model: {model}")
    print(f"Auth: {auth_mode}")
    cache_hit_detected = False

    for run_number in range(1, RUN_COUNT + 1):
        question = QUESTION_TEMPLATE.format(run_number=run_number)
        print(f"Sending request {run_number}...")
        print(f"question={question}")

        elapsed, prompt_tokens, cached_tokens = run_request(client, model, question)
        print(
            f"request_{run_number} latency={elapsed:.2f}s prompt_tokens={prompt_tokens} "
            f"cached_tokens={cached_tokens}"
        )

        if run_number > 1 and cached_tokens > 0:
            cache_hit_detected = True

    if cache_hit_detected:
        print("Result: cache hit detected.")
    else:
        print("Result: cache hit not detected. Make sure the model supports prompt caching.")


if __name__ == "__main__":
    main()
