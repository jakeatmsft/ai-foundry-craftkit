"""Validate modality pricing, missing-data handling, and matched comparisons."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import pytest

PROJECT = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT / "output/jupyter-notebook/gpt_image_token_cost_comparison.ipynb"
MODELS = ["gpt-image-1.5", "gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst"]
COMPONENTS = ["input_text", "input_image", "output_text", "output_image"]


@pytest.fixture
def analysis():
    cells = {
        cell["id"]: "".join(cell["source"]) for cell in json.loads(NOTEBOOK.read_text())["cells"]
    }
    namespace = {
        "Path": Path,
        "json": json,
        "math": math,
        "hashlib": hashlib,
        "pd": pd,
        "MODELS": MODELS,
        "COMPONENTS": COMPONENTS,
        "VOLUME": 1000,
        "display": lambda *args, **kwargs: None,
    }
    for cell_id in ("load-records-helper", "normalise-helper", "pricing-helpers"):
        exec(compile(cells[cell_id], cell_id, "exec"), namespace)
    namespace["cells"] = cells
    namespace["pricing"] = namespace["load_pricing"](
        PROJECT / "assets/gpt_image_reference_rates.json"
    )
    namespace["records"], _ = namespace["load_records"](
        PROJECT / "output/jupyter-notebook/comparisons"
    )
    return namespace


def record_for(analysis, model="gpt-image-1.5", scenario="product"):
    return copy.deepcopy(
        next(
            record
            for record in analysis["records"]
            if record["model"] == model and record["scenario"] == scenario
        )
    )


def test_prices_text_and_image_output_separately(analysis):
    row = analysis["normalise_record"](record_for(analysis))
    cost = analysis["estimate_cost"](row, analysis["pricing"])
    assert row["output_tokens"] == 399
    assert row["output_image"] == 272
    assert row["output_text"] == 127
    assert cost["output_image_usd"] == pytest.approx(0.008704)
    assert cost["output_text_usd"] == pytest.approx(0.00127)
    assert cost["estimated_cost_usd"] == pytest.approx(0.010494)


def test_zero_tokens_allow_unpublished_rate_but_nonzero_tokens_do_not(analysis):
    record = record_for(analysis, "gpt-image-2")
    row = analysis["normalise_record"](record)
    assert analysis["estimate_cost"](row, analysis["pricing"])[
        "estimated_cost_usd"
    ] == pytest.approx(0.0064)
    record["usage"]["output_tokens_details"]["text_tokens"] = 1
    record["usage"]["output_tokens"] += 1
    record["usage"]["total_tokens"] += 1
    cost = analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])
    assert cost["estimated_cost_usd"] is None
    assert "Missing prices: output_text" in cost["cost_issue"]


@pytest.mark.parametrize("change", ["absent", "missing_split", "inconsistent_total"])
def test_missing_or_inconsistent_usage_is_not_zero_cost(analysis, change):
    record = record_for(analysis)
    if change == "absent":
        record["usage"] = None
    elif change == "missing_split":
        del record["usage"]["output_tokens_details"]
    else:
        record["usage"]["output_tokens"] += 1
    row = analysis["normalise_record"](record)
    assert row["usage_issue"]
    assert analysis["estimate_cost"](row, analysis["pricing"])["estimated_cost_usd"] is None


def test_failed_request_is_retained_without_zero_cost(analysis):
    record = record_for(analysis)
    record["status"] = "error"
    cost = analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])
    assert cost["estimated_cost_usd"] is None
    assert "No successful result" in cost["cost_issue"]


def test_deduplicates_manifest_and_sidecar_but_keeps_new_requests(analysis, tmp_path):
    record = record_for(analysis)
    second = copy.deepcopy(record)
    second["request_id"] += "-repeat"
    (tmp_path / "manifest.json").write_text(json.dumps([record, second]))
    (tmp_path / "sidecar.json").write_text(json.dumps(record))
    loaded, audit = analysis["load_records"](tmp_path)
    assert len(loaded) == 2
    assert audit["duplicates_skipped"] == 1


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_rejects_invalid_rates(analysis, tmp_path, value):
    pricing = copy.deepcopy(analysis["pricing"])
    pricing["usd_per_million_tokens"]["gpt-image-1.5"]["input_text"] = value
    path = tmp_path / "rates.json"
    path.write_text(json.dumps(pricing))
    with pytest.raises(ValueError, match="Invalid price"):
        analysis["load_pricing"](path)


def test_balances_repeated_prompts_and_excludes_unmatched_settings(analysis):
    records = copy.deepcopy(analysis["records"])
    records.extend([record_for(analysis) for _ in range(3)])
    different_quality = record_for(analysis)
    different_quality["request"]["quality"] = "high"
    records.append(different_quality)
    analysis["priced"] = pd.DataFrame(
        [
            analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])
            for record in records
        ]
    )
    exec(compile(analysis["cells"]["matched-comparison"], "matched-comparison", "exec"), analysis)
    assert analysis["case_count"] == 5
    assert len(analysis["matched"]) == 23
    expected = (
        sum(
            analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])[
                "estimated_cost_usd"
            ]
            for record in analysis["records"]
            if record["model"] == "gpt-image-1.5"
        )
        / 5
    )
    assert analysis["summary"].loc["gpt-image-1.5", "estimated_cost_usd"] == pytest.approx(expected)


def test_partial_prices_do_not_create_partial_workload_total(analysis):
    pricing = copy.deepcopy(analysis["pricing"])
    pricing["usd_per_million_tokens"]["gpt-image-2"]["input_image"] = None
    analysis["priced"] = pd.DataFrame(
        [
            analysis["estimate_cost"](analysis["normalise_record"](record), pricing)
            for record in analysis["records"]
        ]
    )
    exec(compile(analysis["cells"]["matched-comparison"], "matched-comparison", "exec"), analysis)
    assert analysis["summary"].loc["gpt-image-2", "priced_prompts"] == 4
    assert pd.isna(analysis["summary"].loc["gpt-image-2", "projected_workload_usd"])


def test_unpriced_repeat_does_not_disappear_from_prompt_average(analysis):
    extra = record_for(analysis, "gpt-image-2")
    extra["usage"]["output_tokens_details"]["text_tokens"] = 1
    extra["usage"]["output_tokens"] += 1
    extra["usage"]["total_tokens"] += 1
    analysis["priced"] = pd.DataFrame(
        [
            analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])
            for record in [*analysis["records"], extra]
        ]
    )
    exec(compile(analysis["cells"]["matched-comparison"], "matched-comparison", "exec"), analysis)
    assert analysis["summary"].loc["gpt-image-2", "priced_prompts"] == 4
    assert pd.isna(analysis["summary"].loc["gpt-image-2", "estimated_cost_usd"])


@pytest.mark.parametrize("model", ["MAI-Image-2.6", "MAI-Image-2.6-Flash"])
def test_mai_flat_usage_preserves_totals_without_inventing_output_modality(analysis, model):
    record = record_for(analysis)
    record["model"] = model
    record["request"] = {"model": model, "prompt": "mug", "width": 1024, "height": 1024}
    record["usage"] = {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": 1024}
    row = analysis["normalise_record"](record)
    assert row["input_text"] == row["input_tokens"] == 97
    assert row["input_image"] == 0
    assert row["output_tokens"] == 1024
    assert row["total_tokens"] == 1121
    assert row["output_image"] is row["output_text"] is None
    assert row["usage_available"]
    assert "no reported text/image split" in row["usage_issue"]
    assert row["quality"] == "default (MAI)"
    cost = analysis["estimate_cost"](row, analysis["pricing"])
    assert cost["estimated_cost_usd"] == pytest.approx(0.034277)
    assert cost["output_image_usd"] == pytest.approx(0.033792)
    assert "Assume MAI num_output_tokens" in cost["pricing_usage_basis"]
    assert cost["cost_issue"] == ""
    assert cost["output_image"] is cost["output_text"] is None


def test_mai_does_not_invalidate_matched_gpt_cohorts(analysis):
    record = record_for(analysis)
    record["model"] = "MAI-Image-2.6"
    record["usage"] = {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": 1024}
    analysis["MODELS"] = [*MODELS, "MAI-Image-2.6", "MAI-Image-2.6-Flash"]
    analysis["priced"] = pd.DataFrame([
        analysis["estimate_cost"](analysis["normalise_record"](item), analysis["pricing"])
        for item in [*analysis["records"], record]
    ])
    exec(compile(analysis["cells"]["matched-comparison"], "matched-comparison", "exec"), analysis)
    assert analysis["case_count"] == 5
    assert len(analysis["matched"]) == 20
    assert analysis["summary"].loc["MAI-Image-2.6", "requests_with_usage"] == 1
    assert analysis["usage_summary"].loc["MAI-Image-2.6", "total_tokens"] == 1121
    assert pd.isna(analysis["summary"].loc["MAI-Image-2.6", "estimated_cost_usd"])


@pytest.mark.parametrize("value", [None, -1, True, "1024"])
def test_invalid_mai_output_count_is_not_a_total(analysis, value):
    record = record_for(analysis)
    record["model"] = "MAI-Image-2.6"
    record["usage"] = {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": value}
    row = analysis["normalise_record"](record)
    assert row["total_tokens"] is None
    assert not row["usage_available"]
    assert analysis["estimate_cost"](row, analysis["pricing"])["estimated_cost_usd"] is None


def test_mai_only_input_still_produces_observations(analysis):
    record = record_for(analysis)
    record["model"] = "MAI-Image-2.6"
    record["usage"] = {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": 1024}
    analysis["MODELS"] = [*MODELS, "MAI-Image-2.6", "MAI-Image-2.6-Flash"]
    analysis["priced"] = pd.DataFrame([analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])])
    exec(compile(analysis["cells"]["matched-comparison"], "matched-comparison", "exec"), analysis)
    assert analysis["case_count"] == 0
    assert analysis["usage_summary"].loc["MAI-Image-2.6", "total_tokens"] == 1121
    assert analysis["summary"]["estimated_cost_usd"].isna().all()


@pytest.mark.parametrize("model", ["MAI-Image-2.6", "MAI-Image-2.6-Flash"])
def test_mai_portrait_retains_unpriced_image_input_and_known_subtotal(analysis, model):
    record = record_for(analysis)
    record["model"] = model
    record["usage"] = {"num_input_text_tokens": 123, "num_input_image_tokens": 233, "num_output_tokens": 1023}
    row = analysis["normalise_record"](record)
    cost = analysis["estimate_cost"](row, analysis["pricing"])
    assert cost["estimated_cost_usd"] is None
    assert cost["input_image_usd"] is None
    assert cost["known_component_cost_usd"] == pytest.approx(0.034374)
    assert cost["cost_issue"] == "Missing prices: input_image"
    hypothetical = copy.deepcopy(analysis["pricing"])
    hypothetical["usd_per_million_tokens"][model]["input_image"] = 8.0
    assert analysis["estimate_cost"](row, hypothetical)["estimated_cost_usd"] == pytest.approx(0.036238)


def test_mai_requires_explicit_output_pricing_mapping(analysis):
    record = record_for(analysis)
    record["model"] = "MAI-Image-2.6"
    record["usage"] = {"num_input_text_tokens": 97, "num_input_image_tokens": 0, "num_output_tokens": 1024}
    pricing = copy.deepcopy(analysis["pricing"])
    pricing.pop("mai_output_tokens_as_image_output")
    cost = analysis["estimate_cost"](analysis["normalise_record"](record), pricing)
    assert cost["estimated_cost_usd"] is None
    assert "mapping is not configured" in cost["cost_issue"]


def test_all_model_cost_coverage_and_unpriced_repeats(analysis):
    analysis["MODELS"] = [*MODELS, "MAI-Image-2.6", "MAI-Image-2.6-Flash"]
    records, _ = analysis["load_records"](PROJECT / "output/jupyter-notebook/comparisons")
    analysis["priced"] = pd.DataFrame([
        analysis["estimate_cost"](analysis["normalise_record"](record), analysis["pricing"])
        for record in records
    ])
    exec(compile(analysis["cells"]["all-model-costs"], "all-model-costs", "exec"), analysis)
    summary = analysis["cost_summary"]
    for model in ["MAI-Image-2.6", "MAI-Image-2.6-Flash"]:
        assert summary.loc[model, "prompts"] == 5
        assert summary.loc[model, "priced_prompts"] == 4
        assert summary.loc[model, "average_priced_prompt_usd"] == pytest.approx(0.03426075)
        assert pd.isna(summary.loc[model, "projected_workload_usd"])
    assert analysis["all_per_case"].shape[0] == 30
    repeat = analysis["priced"].loc[
        analysis["priced"]["model"].eq("MAI-Image-2.6") & analysis["priced"]["scenario"].eq("product")
    ].copy()
    repeat["estimated_cost_usd"] = None
    analysis["priced"] = pd.concat([analysis["priced"], repeat], ignore_index=True)
    exec(compile(analysis["cells"]["all-model-costs"], "all-model-costs", "exec"), analysis)
    assert analysis["cost_summary"].loc["MAI-Image-2.6", "priced_prompts"] == 3
