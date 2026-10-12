"""Execute the showcase with the real SDK and an in-memory HTTP transport."""

import base64
import io
import json
from pathlib import Path

import azure.identity
import dotenv
import httpx
import IPython.display
import openai
import pytest
import requests as http_requests
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT / "output/jupyter-notebook/gpt_image_azure_showcase.ipynb"


@pytest.fixture
def notebook_runtime(monkeypatch, tmp_path):
    monkeypatch.chdir(PROJECT)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        azure.identity, "get_bearer_token_provider", lambda *args: lambda: "test-token"
    )
    monkeypatch.setattr(IPython.display, "display", lambda *args, **kwargs: None)
    values = {
        "AZURE_OPENAI_ENDPOINT": "https://primary.openai.azure.com",
        "AZURE_OPENAI_GPT_IMAGE_2_ENDPOINT": "https://secondary.cognitiveservices.azure.com",
        "AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
        "AZURE_OPENAI_GPT_IMAGE_2_API_VERSION": "2025-04-01-preview",
        "GPT_IMAGE_15_DEPLOYMENT": "gpt-image-1.5",
        "GPT_IMAGE_2_DEPLOYMENT": "gpt-image-2",
        "GPT_IMAGE_FLARE_DEPLOYMENT": "gpt-image-2.5-flare",
        "GPT_IMAGE_SUNBURST_DEPLOYMENT": "gpt-image-2.5-sunburst",
        "GPT_IMAGE_OUTPUT_DIR": str(tmp_path),
        "GPT_IMAGE_SIZE": "1024x1024",
        "GPT_IMAGE_QUALITY": "medium",
        "AZURE_MAI_ENDPOINT": "https://mai.services.ai.azure.com",
        "MAI_IMAGE_26_DEPLOYMENT": "MAI-Image-2.6",
        "MAI_IMAGE_26_FLASH_DEPLOYMENT": "MAI-Image-2.6-Flash",
        "MAI_IMAGE_WIDTH": "1024",
        "MAI_IMAGE_HEIGHT": "1024",
        "MAI_IMAGE_MIN_INTERVAL_SECONDS": "0",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), (200, 100, 50, 0)).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    requests = []
    controls = {"status": 200, "image": encoded, "usage": True}

    def respond(request):
        requests.append(request)
        if controls["status"] != 200:
            return httpx.Response(
                controls["status"],
                json={"error": {"code": "test_failure", "message": "Simulated service error"}},
                headers={"x-request-id": "failed-request"},
            )
        body = {"created": 1, "data": [{"b64_json": controls["image"]}]}
        if controls["usage"]:
            body["usage"] = (
                {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": 1024}
                if request.url.path.startswith("/mai/")
                else {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
            )
        return httpx.Response(200, json=body, headers={"x-request-id": "test-request"})

    real_client = openai.AzureOpenAI

    def client_factory(**kwargs):
        return real_client(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )

    monkeypatch.setattr(openai, "AzureOpenAI", client_factory)

    def send_mai(session, prepared, **kwargs):
        # Exercise real requests JSON/multipart serialization without a network call.
        req = httpx.Request(prepared.method, prepared.url, headers=prepared.headers, content=prepared.body)
        reply = respond(req)
        response = http_requests.Response()
        response.status_code = reply.status_code
        response.headers.update(reply.headers)
        response._content = reply.content
        response.url = prepared.url
        response.request = prepared
        return response

    monkeypatch.setattr(http_requests.Session, "send", send_mai)
    notebook = json.loads(NOTEBOOK.read_text())
    namespace = {}

    def execute(*ids):
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code" and (not ids or cell["id"] in ids):
                exec(compile("".join(cell["source"]), cell["id"], "exec"), namespace)

    yield namespace, requests, controls, execute
    for client in namespace.get("clients", {}).values():
        client.close()


def test_all_cells_route_models_upload_portrait_and_save_outputs(notebook_runtime):
    namespace, requests, _, execute = notebook_runtime
    execute()
    assert len(requests) == namespace["request_count"] == 30
    assert len(namespace["RUN_LOG"]) == 30
    assert all(record["status"] == "ok" for record in namespace["RUN_LOG"])
    edits = []
    for request in requests:
        is_mai = request.url.path.startswith("/mai/")
        deployment = request.url.path.split("/")[3] if not is_mai else None
        expected_host = (
            "mai.services.ai.azure.com" if is_mai
            else "secondary.cognitiveservices.azure.com" if deployment == "gpt-image-2"
            else "primary.openai.azure.com"
        )
        assert request.url.host == expected_host
        if is_mai:
            assert not request.url.query
            assert request.url.path in {"/mai/v1/images/generations", "/mai/v1/images/edits"}
        else:
            assert request.url.params["api-version"] == "2025-04-01-preview"
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path.endswith("/edits"):
            edits.append(request)
            assert "multipart/form-data" in request.headers["content-type"]
            assert (PROJECT / "assets/reference_portrait.png").read_bytes() in request.content
            assert b"input_fidelity" not in request.content
            if is_mai:
                for field in ["quality", "background", "n", "size", "width", "height", "output_format"]:
                    assert f'name="{field}"'.encode() not in request.content
                assert b'name="auto_aspect_ratio"\r\n\r\nfalse' in request.content
                assert b'name="web_grounding"\r\n\r\nfalse' in request.content
        else:
            payload = json.loads(request.content)
            if is_mai:
                assert payload["model"] in namespace["MAI_MODELS"]
                assert payload["width"] == payload["height"] == 1024
                assert payload["auto_aspect_ratio"] is payload["web_grounding"] is False
                assert not {"quality", "size", "background", "n", "output_format"} & payload.keys()
            else:
                assert payload["model"] == deployment
                assert payload["n"] == 1
            assert "response_format" not in payload
            assert "output_compression" not in payload
    assert len(edits) == 6
    run_dir = namespace["RUN_DIR"]
    assert len(list(run_dir.glob("*.png"))) == 30
    assert len(json.loads((run_dir / "manifest.json").read_text())) == 30
    assert all(record["has_transparency"] for record in namespace["cutouts"])
    assert all(record["request_id"] == "test-request" for record in namespace["RUN_LOG"])
    comparisons = run_dir / "comparisons"
    expected = {"product", "poster", "illustration", "portrait_astronaut", "transparent_mascot"}
    assert {path.stem.removesuffix("_comparison") for path in comparisons.glob("*.png")} == expected
    html = (comparisons / "index.html").read_text()
    for scenario in expected:
        assert f'id="{scenario}"' in html
        assert f"{scenario}_comparison.png" in html
        metadata = json.loads((comparisons / f"{scenario}.json").read_text())
        assert all(
            record["request"]["prompt"] == metadata["prompt"] for record in metadata["results"]
        )
    with Image.open(comparisons / "portrait_astronaut_comparison.png") as image:
        assert image.width == 7 * 384  # Original plus all six models.
    transparent = json.loads((comparisons / "transparent_mascot.json").read_text())
    assert transparent["omitted_models"] == []
    assert {record["model"] for record in transparent["results"]} == set(namespace["DEPLOYMENTS"])
    with Image.open(comparisons / "transparent_mascot_comparison.png") as image:
        assert image.width == 6 * 384


@pytest.mark.parametrize("model", ["gpt-image-2", "MAI-Image-2.6"])
@pytest.mark.parametrize("status", [400, 404, 429, 500])
def test_service_errors_are_recorded_without_retry_or_stale_images(notebook_runtime, status, model):
    namespace, requests, controls, execute = notebook_runtime
    execute("configuration", "request-helper")
    make_image = namespace["make_image"]
    first = make_image(model, "test", "A ceramic mug")
    controls["status"] = status
    failed = make_image(model, "test", "A ceramic mug")
    controls["status"] = 200
    last = make_image("gpt-image-2.5-flare", "test", "A ceramic mug")
    assert first["status"] == last["status"] == "ok"
    assert first["image_path"] != last["image_path"]
    assert failed["status"] == "error"
    assert failed["http_status"] == status
    assert failed["request_id"] == "failed-request"
    assert "image_path" not in failed
    assert len(requests) == 3
    assert len(list(namespace["RUN_DIR"].glob("*.png"))) == 2
    execute("gallery-helper")
    namespace["show_gallery"]([first, failed, last], "Failure comparison")
    assert len(requests) == 3  # Rendering uses saved results without regenerating images.
    metadata = json.loads((namespace["RUN_DIR"] / "comparisons" / "test.json").read_text())
    assert metadata["results"][1]["status"] == "error"
    assert "image_path" not in metadata["results"][1]


def test_invalid_base64_and_missing_usage(notebook_runtime):
    namespace, _, controls, execute = notebook_runtime
    execute("configuration", "request-helper")
    controls["usage"] = False
    result = namespace["make_image"]("gpt-image-1.5", "no_usage", "A ceramic mug")
    assert result["status"] == "ok"
    assert result["usage"] is None
    controls["image"] = "invalid-base64!"
    result = namespace["make_image"]("gpt-image-1.5", "bad_image", "A ceramic mug")
    assert result["status"] == "error"
    assert "image_path" not in result


def test_second_resource_is_required(notebook_runtime, monkeypatch):
    _, requests, _, execute = notebook_runtime
    monkeypatch.delenv("AZURE_OPENAI_GPT_IMAGE_2_ENDPOINT")
    with pytest.raises(ValueError, match="AZURE_OPENAI_GPT_IMAGE_2_ENDPOINT"):
        execute("configuration")
    assert requests == []


@pytest.mark.parametrize("width,height", [(1536, 1024), (767, 1024)])
def test_mai_dimensions_fail_before_any_network_request(notebook_runtime, monkeypatch, width, height):
    _, requests, _, execute = notebook_runtime
    monkeypatch.setenv("MAI_IMAGE_WIDTH", str(width))
    monkeypatch.setenv("MAI_IMAGE_HEIGHT", str(height))
    with pytest.raises(ValueError, match="MAI dimensions"):
        execute("configuration")
    assert not requests


def test_mai_missing_usage_stays_unavailable(notebook_runtime):
    namespace, _, controls, execute = notebook_runtime
    execute("configuration", "request-helper")
    controls["usage"] = False
    record = namespace["make_image"]("MAI-Image-2.6-Flash", "test", "A ceramic mug")
    assert record["status"] == "ok"
    assert record["usage"] is None
    assert record["api_version"] is None


def test_flare_quality_sweep_sends_low_through_xhigh_with_same_prompt(notebook_runtime):
    namespace, requests, _, execute = notebook_runtime
    execute("configuration", "demo-scope", "request-helper", "gallery-helper", "prompts")
    namespace["RUN_QUALITY_SWEEP"] = True
    namespace["QUALITY_REQUEST_INTERVAL_SECONDS"] = 0
    execute("quality-exercise")
    payloads = [json.loads(request.content) for request in requests]
    assert [p["quality"] for p in payloads] == ["low", "medium", "high", "xhigh"]
    assert {p["model"] for p in payloads} == {"gpt-image-2.5-flare"}
    assert len({p["prompt"] for p in payloads}) == 1
    assert len({p["size"] for p in payloads}) == 1
    assert all(request.url.host == "primary.openai.azure.com" for request in requests)
    sheet = namespace["RUN_DIR"] / "comparisons/flare_quality_sweep_comparison.png"
    with Image.open(sheet) as image:
        assert image.width == 4 * 384
