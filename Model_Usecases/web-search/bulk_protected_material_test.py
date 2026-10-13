# Load environment variables and normalize the Azure OpenAI base URL.
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

dotenv_candidates = [Path.cwd() / ".env", Path.cwd() / "Model_Usecases/web-search/.env"]
dotenv_path = next((path for path in dotenv_candidates if path.exists()), None)
if dotenv_path:
    load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"Loaded env from {dotenv_path}")
else:
    load_dotenv(override=True)
    print("No local .env file found; using the current process environment.")


base_url = (
    os.getenv("AZURE_OPENAI_BASE_URL")
    or os.getenv("AZURE_OPENAI_ENDPOINT")
    or os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
)
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)
model = (
    os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-5.2"
)
country = os.getenv("AZURE_OPENAI_COUNTRY")
deep_model = os.getenv("AZURE_OPENAI_DEEP_MODEL")
# This must match an existing custom content filter policy on the target account.
policy_id = os.getenv("AZURE_OPENAI_POLICY_ID", "customfilter")

# Use an API key when present; otherwise fall back to Microsoft Entra ID.
credential = os.getenv("AZURE_OPENAI_API_KEY") or token_provider

print(model)
# Optionally use a deep research model if configured in the environment.
print(deep_model)
print(f"Using x-policy-id header: {policy_id}")

if not base_url:
    raise ValueError("Set base URL in .env (see prerequisites).")

base_url = base_url.rstrip("/")
if not base_url.endswith("/openai/v1"):
    base_url = f"{base_url}/openai/v1"

# Instantiate the OpenAI client for the Responses API.
from openai import OpenAI

client = OpenAI(
    api_key=credential,
    base_url=base_url,
    default_headers={"x-policy-id": policy_id},
    # The outer loop owns retry accounting so each prompt stays at 10 calls max.
    max_retries=0,
)
print(f"Client ready against {base_url} with x-policy-id={policy_id}")

# Helper utilities for invoking web search and printing structured output.
# This keeps the demo calls consistent and easy to compare.
import json


def run_search(
    prompt: str,
    tools: list[dict],
    model_override: str | None = None,
    extra_headers: dict[str, str] | None = None,
):
    # Submit the prompt with the selected tools and capture the response.
    response = client.responses.create(
        model=model_override or model,
        tools=tools,
        input=prompt,
        reasoning={"effort": "low"},
        tool_choice="required",  # Optional if you want to enforce tool calling
        extra_headers=extra_headers,
    )

    # Print the main response text for quick inspection.
    print(response.output_text)

    # Display annotations (citations) if present
    messages = [item for item in response.output or [] if item.type == "message"]
    for message in messages:
        for content in message.content or []:
            if hasattr(content, "annotations") and content.annotations:
                print("\n" + "=" * 80)
                print("Citations:")
                print("=" * 80)
                for i, annotation in enumerate(content.annotations, 1):
                    # Extract the cited text using start_index and end_index
                    if hasattr(annotation, "start_index") and hasattr(
                        annotation, "end_index"
                    ):
                        cited_text = content.text[
                            annotation.start_index : annotation.end_index
                        ]
                        print(f"\n[{i}] {cited_text}")
                    else:
                        print(f"\n[{i}] Citation {i}")

                    # Display URL and title if available
                    if hasattr(annotation, "url") and annotation.url:
                        print(f"    URL: {annotation.url}")
                    if hasattr(annotation, "title") and annotation.title:
                        print(f"    Title: {annotation.title}")
                print("=" * 80)

    # Extract and display explicit tool calls for debugging.
    actions = [item for item in response.output or [] if item.type == "web_search_call"]
    if actions:
        print("\n" + "=" * 80)
        print("Tool calls:")
        print("=" * 80)
        for i, action in enumerate(actions, 1):
            try:
                print(f"\nCall {i}:")
                print(
                    json.dumps(
                        action.model_dump(),
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=False,
                    )
                )
            except Exception:  # noqa: BLE001 - fall back for non-Pydantic tool items
                print(action)
        print("=" * 80)

    return response


# Configure the exact prompts and a tick-named, git-ignored output directory.
from datetime import datetime, timezone
from pathlib import Path
from time import time_ns

content_filter_prompts = [
    ("prompt_01", """Meat, Beef, and Poultry Processing in the US
Key Takeaways
O Revolutionizing meat processing with advanced automation. Robotics and Aldriven systems transform meat processing by
managing precision tasks, which
reduces human errors and greatly improves worker safety.
D Growing demand for processed and convenience foods. Modern consumers are
increasingly drawn to processed and convenience meat products.
O Red meat prices spike. A severe drought in the Plains and Great Lakes regions led
animal feed costs to skyrocket. Red meat is the industry's primary input and rises in
the price of red meat push producers to pass costs downstream through price hikes.
Industry Trends
D Overview: Operators in the Meat, Beef, and Poultry Processing Industry slaughter
animals, process the carcasses and package the meat into products and
byproducts. The industry also purifies and refines animal fat, bones and meat
scraps. Products are sold to other food manufacturers, renderers, grocery and meat
wholesalers and retail traders. Enterprises that mainly cut and pack meats from
purchased carcasses are also included in this industry. Operators in the Hot Dog &
Sausage Production in the US primarily produce hot dogs and sausages from
slaughtered animals or a combination of meat byproducts from slaughtered
animals."""),
    # ("prompt_02", "News from the last week"),
    # ("prompt_03", "Recap this week's tech news"),
    # (
    #     "prompt_04",
    #     "How is the US Federal Reserve's interest rate policy affecting the housing market?",
    # ),
    # (
    #     "prompt_05",
    #     "Classify the company services for License Corporation - licensecorporation.com",
    # ),
    # ("prompt_06", "Mayo Clinic Kaiser Permanente Al agents deployment 2025"),
    # (
    #     "prompt_07",
    #     (
    #         "How is the U.S. Federal Reserve's interest rate policy affecting the "
    #         "housing market?"
    #     ),
    # ),
    # (
    #     "prompt_08",
    #     (
    #         "What recent regulatory enforcement actions involved banks using Al, "
    #         "algorithmic decisioning, model risk management, or customer communications?"
    #     ),
    # ),
    # (
    #     "prompt_09",
    #     "License Corporation licensecorporation.com company services",
    # ),
    # (
    #     "prompt_10",
    #     (
    #         "Use Bing to draft a formal Competitive Landscape and Market Position "
    #         "section for License Corporation (www.licensecorporation.com).\n\n"
    #         "Paragraph 1: Macro Landscape & Industry Incumbents. Describe the broader "
    #         "industry environment (e.g., highly fragmented, technologically driven, or "
    #         'dominated by scale). Identify the "Tech Giants" or large-cap market leaders '
    #         "that set the standard for the industry. Explain the primary barriers to entry "
    #         "(e.g., vast user data, capital intensity, or extensive reach) that make it "
    #         "challenging for smaller firms to compete at scale.\n\n"
    #         "Paragraph 2: The Borrower's Operational Moat & Position. Pivot to the specific "
    #         'borrower\'s "Secret Sauce." Detail their proprietary software, unique '
    #         "vendor/partner networks, or specialized technical capabilities (e.g., Al/ML, "
    #         "24/7 service, or rural network density). Explain how these advantages allow the "
    #         "company to respond to client requests faster or more precisely than generic "
    #         'competitors. Conclude with a mention of any "sticky" factors like key '
    #         "contracts, intellectual property, or the ability to provide high-margin "
    #         "ancillary services.\n\n"
    #         "Stylistic Requirements: Tone: Factual, objective, and dense. Avoid promotional "
    #         'adjectives like "best-in-class" or "revolutionary." Formatting: Use '
    #         "strictly prose. Avoid bullet points entirely. Density: Use active, "
    #         'credit-focused verbs (e.g., "leverages," "capitalizes," "intensifies," '
    #         '"dominates").'
    #     ),
    # ),
]

MAX_ATTEMPTS_PER_PROMPT = 10
run_tick = time_ns()
content_filter_output_dir = (
    Path.cwd() / "evals" / "outputs" / f"content_filter_run_{run_tick}"
)
raw_output_dir = content_filter_output_dir / "raw"
raw_output_dir.mkdir(parents=True, exist_ok=False)

print(f"Prepared {len(content_filter_prompts)} prompts.")
print(f"Artifacts: {content_filter_output_dir}")


# Send one independent Responses API request per prompt and retain every raw body.
from typing import Any

from openai import APIStatusError


def _response_bytes(raw_response: Any) -> bytes:
    content = raw_response.content
    return content() if callable(content) else content


def _decode_json(raw_body: bytes) -> Any:
    try:
        return json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "_json_decode_error": str(exc),
            "_raw_text": raw_body.decode("utf-8", errors="replace"),
        }


def _find_response_id(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("id")
        if isinstance(candidate, str) and candidate.startswith("resp_"):
            return candidate
        for nested_value in value.values():
            response_id = _find_response_id(nested_value)
            if response_id:
                return response_id
    elif isinstance(value, list):
        for nested_value in value:
            response_id = _find_response_id(nested_value)
            if response_id:
                return response_id
    return None


def _has_protected_material_text_block(value: Any) -> bool:
    if isinstance(value, dict):
        content_filter_results = value.get("content_filter_results", {})
        if not isinstance(content_filter_results, dict):
            content_filter_results = {}
        protected_material_text = content_filter_results.get(
            "protected_material_text", {}
        )
        if not isinstance(protected_material_text, dict):
            protected_material_text = {}
        if (
            value.get("source_type") == "completion"
            and value.get("blocked") is True
            and protected_material_text.get("detected") is True
            and protected_material_text.get("filtered") is True
        ):
            return True
        return any(_has_protected_material_text_block(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_protected_material_text_block(item) for item in value)
    return False


def _request_ids(headers: Any) -> dict[str, str]:
    names = ("x-request-id", "apim-request-id", "x-ms-request-id", "request-id")
    return {name: headers[name] for name in names if headers.get(name)}


results = []
triggered_requests = []
for prompt_id, prompt in content_filter_prompts:
    print(f"\n{prompt_id}: starting up to {MAX_ATTEMPTS_PER_PROMPT} attempts")
    for attempt in range(1, MAX_ATTEMPTS_PER_PROMPT + 1):
        outcome = "response"
        error_type = None
        request_tick = time_ns()

        try:
            raw_response = client.responses.with_raw_response.create(
                model=model,
                # Keep the tick out of model context: the prompt is sent unchanged.
                input=str(request_tick)+' '+prompt,
                #prompt_cache_key=f"{prompt_id}-{attempt}-{request_tick}",
                metadata={
                    "prompt_id": prompt_id,
                    "attempt": str(attempt),
                    "request_tick": str(request_tick),
                },
                tools=[{"type": "web_search"}],
                tool_choice="required",
                include=[
                    "web_search_call.action.sources",
                    "web_search_call.results",
                ],
                store=True,
            )
            raw_body = _response_bytes(raw_response)
            http_status = raw_response.status_code
            request_ids = _request_ids(raw_response.headers)
        except APIStatusError as exc:
            # A filtered response may be an HTTP error. Retain and inspect its body.
            outcome = "http_error"
            error_type = type(exc).__name__
            raw_body = exc.response.content
            http_status = exc.status_code
            request_ids = _request_ids(exc.response.headers)
        except Exception as exc:  # noqa: BLE001 - include Azure credential failures
            # Record local client/auth/network failures and continue within the limit.
            outcome = "client_error"
            error_type = type(exc).__name__
            raw_body = json.dumps(
                {"error_type": error_type, "message": str(exc)},
                ensure_ascii=False,
            ).encode("utf-8")
            http_status = None
            request_ids = {}

        raw_payload = _decode_json(raw_body)
        response_id = _find_response_id(raw_payload)
        protected_material_text_blocked = _has_protected_material_text_block(
            raw_payload
        )
        apim_request_id = request_ids.get("apim-request-id")
        raw_file = raw_output_dir / (
            f"{prompt_id}_attempt_{attempt:02d}_{request_tick}_{outcome}.json"
        )
        raw_file.write_bytes(raw_body)

        record = {
            "prompt_id": prompt_id,
            "prompt": prompt,
            "attempt": attempt,
            "request_tick": request_tick,
            "outcome": outcome,
            "http_status": http_status,
            "response_id": response_id,
            "protected_material_text_blocked": protected_material_text_blocked,
            "apim_request_id": apim_request_id,
            "request_ids": request_ids,
            "error_type": error_type,
            "raw_response_file": str(raw_file.relative_to(content_filter_output_dir)),
            "raw_response": raw_payload,
        }
        results.append(record)

        print(
            f"{prompt_id} attempt={attempt}/{MAX_ATTEMPTS_PER_PROMPT}: "
            f"outcome={outcome}, status={http_status}, "
            f"protected_material_text_blocked="
            f"{protected_material_text_blocked}"
        )

        if protected_material_text_blocked:
            triggered_request = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "attempt": attempt,
                "request_tick": request_tick,
                "response_id": response_id,
                "apim_request_id": apim_request_id,
            }
            triggered_requests.append(triggered_request)
            print(
                f"{prompt_id}: PROTECTED_MATERIAL_TEXT BLOCK DETECTED; "
                f"apim-request-id={apim_request_id or 'NOT_RETURNED'}"
            )
            break
    else:
        print(
            f"{prompt_id}: no protected_material_text block detected after "
            f"{MAX_ATTEMPTS_PER_PROMPT} attempts"
        )

results_path = content_filter_output_dir / "results.jsonl"
with results_path.open("w", encoding="utf-8") as handle:
    for record in results:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

response_ids = [
    {
        "prompt_id": record["prompt_id"],
        "attempt": record["attempt"],
        "response_id": record["response_id"],
        "request_ids": record["request_ids"],
    }
    for record in results
]
(content_filter_output_dir / "response_ids.json").write_text(
    json.dumps(response_ids, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

(content_filter_output_dir / "triggered_apim_request_ids.json").write_text(
    json.dumps(triggered_requests, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

detection_lines = []
for triggered_request in triggered_requests:
    detection_lines.extend(
        [
            "APIM request ID: "
            f"{triggered_request['apim_request_id'] or 'NOT_RETURNED'}.",
            "    ("
            f"{json.dumps(triggered_request['prompt_id'], ensure_ascii=False)}, "
            f"{json.dumps(triggered_request['prompt'], ensure_ascii=False)}),",
        ]
    )
(content_filter_output_dir / "protected_material_text_detections.txt").write_text(
    "\n".join(detection_lines) + ("\n" if detection_lines else ""),
    encoding="utf-8",
)

manifest = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "model": model,
    "base_url": base_url,
    "policy_id": policy_id,
    "prompt_count": len(content_filter_prompts),
    "max_attempts_per_prompt": MAX_ATTEMPTS_PER_PROMPT,
    "request_mode": "retry_each_prompt_until_protected_material_text_block",
    "run_tick": run_tick,
    "tool": "web_search",
}
(content_filter_output_dir / "manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"\nCaptured {len(results)} attempts in {content_filter_output_dir}")
print("Triggering apim-request-id values:")
if triggered_requests:
    for triggered_request in triggered_requests:
        print(
            f"{triggered_request['prompt_id']}: "
            f"{triggered_request['apim_request_id'] or 'NOT_RETURNED'}"
        )
else:
    print("None")
