# Web Search Tool Usage (OpenAI Python SDK)

This guide summarizes how the `web_search` tool is used via the OpenAI Python SDK Responses API, based on the implementation in `web_search_demo.ipynb`. The workflow uses a single `OpenAI` client, passes the `web_search` tool in the `tools` list, and then inspects the structured response for the assistant answer, tool calls, and citations.

## High-level flow

1. Load environment variables and construct an `OpenAI` client.
2. Call `client.responses.create(...)` with `tools=[{"type": "web_search"}]`.
3. Read the assistant’s answer from `response.output_text`.
4. Inspect `response.output` for `web_search_call` items and citation annotations.

## Minimal usage example

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

base_url = (
    os.getenv("AZURE_OPENAI_BASE_URL")
    or os.getenv("AZURE_OPENAI_API_BASE")
    or os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
)
api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-5.2"

if not base_url or not api_key:
    raise ValueError("Set base URL and API key in .env (see prerequisites).")

base_url = base_url.rstrip("/")
if not base_url.endswith("/openai/v1"):
    base_url = f"{base_url}/openai/v1"

client = OpenAI(api_key=api_key, base_url=base_url)

response = client.responses.create(
    model=model,
    tools=[{"type": "web_search"}],
    input="What happened in the last NFL game?",
    tool_choice="required", #Optional if you want to enforce tool calling
)

print(response.output_text)
```

## Tool configuration patterns

### Location-biased search
Use `user_location` to bias results to a region. The demo uses `approximate` country-only targeting.

```python
location_tools = [
    {
        "type": "web_search",
        "user_location": {"type": "approximate", "country": "US"},
    }
]

response = client.responses.create(
    model=model,
    tools=location_tools,
    input="Share a positive news story from the web today.",
)
```

### Domain filtering
Limit searches to a curated list of sources with `filters.allowed_domains`.

```python
filtered_tools = [
    {
        "type": "web_search",
        "filters": {
            "allowed_domains": [
                "pubmed.ncbi.nlm.nih.gov",
                "clinicaltrials.gov",
                "www.who.int",
                "www.cdc.gov",
                "www.fda.gov",
            ]
        },
    }
]

response = client.responses.create(
    model=model,
    tools=filtered_tools,
    input="Please perform a web search on how semaglutide is used in the treatment of diabetes.",
)
```

## Reading tool calls

The Responses API emits tool call entries in `response.output` with `type == "web_search_call"`. The demo filters those items and prints the serialized payload for debugging.

```python
tool_calls = [item for item in response.output or [] if item.type == "web_search_call"]
for call in tool_calls:
    print(call.model_dump())
```

Each `web_search_call` typically includes:

- The search query or queries the model generated.
- Tool call status (e.g., `completed`).
- Any tool-specific metadata needed for auditing or replay.

## Reading citations and sources

The assistant’s response content may include `annotations` that represent citations. Each annotation contains `start_index` and `end_index` offsets into the response text, plus URL and title metadata. The demo extracts those spans to display cited text alongside source links.

```python
messages = [item for item in response.output or [] if item.type == "message"]
for message in messages:
    for content in message.content or []:
        if hasattr(content, "annotations") and content.annotations:
            for annotation in content.annotations:
                cited_text = content.text[annotation.start_index:annotation.end_index]
                print(cited_text)
                print(annotation.url, annotation.title)
```

Some responses may also surface `sources` on output items. The demo aggregates these into a list to print a summary of consulted sources.

## Notes and best practices

- `response.output_text` is the simplest way to read the final answer.
- Keep the `tools` list explicit so you can switch between plain generation and tool-augmented responses.
- For reproducibility in demos, pass a fixed `model` (and optionally a `model_override` when comparing behaviors).
- Use location bias and allowed domain filters to meet compliance or regional relevance requirements.
