"""Render the saved four-level Flare quality comparison without API requests.

Requires the showcase and cost notebook dependencies. Input:
output/jupyter-notebook/comparisons/flare-quality/results.json
Run render_comparison_charts.py afterward to refresh the interactive graphs.
"""

import hashlib
import json
import math
import re
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / "output/jupyter-notebook"
OUTPUT = BASE / "comparisons/flare-quality"
manifest_path = OUTPUT / "results.json"
manifest = json.loads(manifest_path.read_text())
records = manifest["results"]
qualities = ["low", "medium", "high", "xhigh"]
assert [r["request"]["quality"] for r in records] == qualities
assert {r["model"] for r in records} == {"gpt-image-2.5-flare"}
assert (
    len(
        {
            json.dumps({k: v for k, v in r["request"].items() if k != "quality"}, sort_keys=True)
            for r in records
        }
    )
    == 1
)

# Reuse the same normalization and pricing functions as the validated cost notebook.
namespace = {
    "json": json,
    "math": math,
    "hashlib": hashlib,
    "Path": Path,
    "COMPONENTS": ["input_text", "input_image", "output_text", "output_image"],
}
notebook = json.loads((BASE / "gpt_image_token_cost_comparison.ipynb").read_text())
for cell in notebook["cells"]:
    if cell["id"] in ["normalise-helper", "pricing-helpers"]:
        exec(compile("".join(cell["source"]), cell["id"], "exec"), namespace)
pricing = namespace["load_pricing"](BASE / "cost-analysis/pricing_used.json")
rows = [
    namespace["estimate_cost"](
        namespace["normalise_record"]({**r, "source_file": str(manifest_path)}), pricing
    )
    for r in records
]
(OUTPUT / "metrics.json").write_text(
    json.dumps({"model": manifest["model"], "pricing": pricing, "results": rows}, indent=2) + "\n"
)

sheet = Image.new("RGB", (384 * 4, 476), "#f8fafc")
draw = ImageDraw.Draw(sheet)
font, small = ImageFont.load_default(size=22), ImageFont.load_default(size=16)
cards = []
for index, (record, row) in enumerate(zip(records, rows)):
    quality = row["quality"]
    left = index * 384
    draw.text((left + 12, 12), quality.upper(), fill="#0f172a", font=font)
    if record["status"] == "ok":
        with Image.open(PROJECT / record["image_path"]) as original:
            preview = ImageOps.contain(original.convert("RGB"), (360, 360))
        sheet.paste(preview, (left + 12, 52))
        image_html = f'<a href="flare-quality/{quality}.png" target="_blank" rel="noopener"><img src="flare-quality/{quality}.png" alt="GPT Image 2.5 Flare product image at {quality} quality" loading="lazy" width="1024" height="1024"></a>'
    else:
        image_html = (
            '<p class="quality-error">' + escape(record.get("error", "Request failed")) + "</p>"
        )
        draw.text((left + 12, 72), "Request failed", fill="#92400e", font=small)
    cost = row["estimated_cost_usd"]
    cost_text = "Unavailable" if cost is None else f"${cost:.5f}"
    draw.text(
        (left + 12, 428),
        f"{record['elapsed_seconds']:.2f} s | {cost_text}",
        fill="#334155",
        font=small,
    )
    cards.append(
        f'<figure class="flare-quality-card"><figcaption><strong>{quality.upper()}</strong><span>{cost_text} estimated · {record["elapsed_seconds"]:.2f} s</span></figcaption>{image_html}</figure>'
    )
sheet.save(OUTPUT / "quality_comparison.png")
headers = [
    "Quality",
    "Size",
    "Input text tokens",
    "Image-output tokens",
    "Text-output tokens",
    "Total tokens",
    "Seconds",
    "Estimated total USD",
]
body = ""
for row in rows:
    values = [
        row["quality"],
        row["size"],
        row["input_text"],
        row["output_image"],
        row["output_text"],
        row["total_tokens"],
        f"{row['elapsed_seconds']:.2f}",
        "—" if row["estimated_cost_usd"] is None else f"${row['estimated_cost_usd']:.6f}",
    ]
    body += (
        "<tr>"
        + "".join(
            f"<{'th' if i == 0 else 'td'}>{escape(str(value))}</{'th' if i == 0 else 'td'}>"
            for i, value in enumerate(values)
        )
        + "</tr>"
    )
rate = pricing["usd_per_million_tokens"][manifest["model"]]
section = (
    '<section id="flare-quality"><h2>GPT Image 2.5 Flare: low → xhigh</h2>'
    "<p>Four fresh generations of the same ORBIT product prompt at <strong>1024 × 1024</strong>. "
    "Only the quality setting changes: <strong>low, medium, high, xhigh</strong>. "
    "One sample per level illustrates image detail, token usage, latency, and estimated cost; generation is stochastic.</p>"
    f"<p><strong>Prompt:</strong> {escape(manifest['prompt'])}</p>"
    '<div class="flare-quality-grid">' + "".join(cards) + "</div>"
    '<p><a href="flare-quality/quality_comparison.png" download>Download the four-quality comparison PNG</a> · '
    '<a href="flare-quality/results.json">Request metadata</a></p>'
    "<h3>Observed usage and cost by quality</h3>"
    '<div class="pricing-table-scroll"><table class="pricing-table"><caption>One successful image per quality level</caption><thead><tr>'
    + "".join("<th>" + heading + "</th>" for heading in headers)
    + "</tr></thead><tbody>"
    + body
    + "</tbody></table></div>"
    f"<p>Reference estimates use ${rate['input_text']:g} per million text-input tokens and ${rate['output_image']:g} per million image-output tokens; no text-output tokens were returned. "
    "Costs include both input and output tokens. These are reference estimates, not verified Azure invoice amounts.</p>"
    "<p>This separate quality experiment is excluded from the five-prompt, six-model averages below. "
    "The supplied Apidog quality-price table remains a separate reference. Rate-limited attempts are retained in the request metadata; the images shown are successful calls.</p>"
    "</section>"
)
page = BASE / "comparisons/index.html"
html = page.read_text()
if re.search(r'<section id="flare-quality">', html):
    html = re.sub(r'<section id="flare-quality">.*?</section>', lambda _: section, html, flags=re.S)
else:
    html = html.replace(
        '<section id="api-differences">', section + '<section id="api-differences">', 1
    )
if 'href="#flare-quality"' not in html:
    html = html.replace("</nav>", ' · <a href="#flare-quality">Flare low → xhigh</a></nav>', 1)
styles = """<style id="flare-quality-styles">
.flare-quality-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}
.flare-quality-card{margin:0;border:1px solid #dbe3ee;border-radius:10px;overflow:hidden;background:#f8fafc}
.flare-quality-card figcaption{padding:14px;display:flex;flex-direction:column;gap:4px}.flare-quality-card figcaption span{font-size:14px;color:#475569}
.flare-quality-card img{width:100%;height:auto;display:block}.quality-error{padding:16px;overflow-wrap:anywhere}
@media(max-width:1000px){.flare-quality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:540px){.flare-quality-grid{grid-template-columns:minmax(0,1fr)}}
</style>"""
html = re.sub(r'<style id="flare-quality-styles">.*?</style>', "", html, flags=re.S)
html = html.replace("<h1>", styles + "<h1>", 1)
page.write_text(html)
print(f"Rendered Flare low/medium/high/xhigh images and measured metrics: {page}")
