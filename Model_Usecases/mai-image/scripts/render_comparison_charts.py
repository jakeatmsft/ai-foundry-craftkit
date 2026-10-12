"""Refresh the gallery's offline charts from saved analysis files and the Apidog table.

Run after executing the cost notebook:
    python scripts/render_comparison_charts.py
Requires requirements-image-costs.txt. Makes no model or network requests.
"""

import json
import re
from html import escape, unescape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / "output/jupyter-notebook"
GALLERY = BASE / "comparisons"
PAGE = GALLERY / "index.html"
html = PAGE.read_text(encoding="utf-8")
usage = pd.read_csv(BASE / "cost-analysis/all_model_usage_summary.csv").set_index("model")
summary = pd.read_csv(BASE / "cost-analysis/model_summary.csv").set_index("model")
prompts = pd.read_csv(BASE / "cost-analysis/all_model_prompt_costs.csv")
pricing = json.loads((BASE / "cost-analysis/pricing_used.json").read_text(encoding="utf-8"))
models = usage.index.tolist()
labels = [
    "GPT Image 1.5",
    "GPT Image 2",
    "GPT 2.5 Flare",
    "GPT 2.5 Sunburst",
    "MAI 2.6",
    "MAI 2.6 Flash",
]
assert len(models) == len(labels) == 6
model_colors = ["#2563eb", "#3b82f6", "#6366f1", "#8b5cf6", "#0f766e", "#14b8a6"]
charts = []


def chart(figure, chart_id, title, description, *, height=430, **layout):
    figure.update_layout(
        template="none",
        autosize=True,
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="system-ui, sans-serif", size=12, color="#334155"),
        margin=dict(l=135, r=65, t=55, b=65),
        legend=dict(orientation="h", y=1.15, x=0, itemclick=False, itemdoubleclick=False),
        hoverlabel=dict(bgcolor="#0f172a", font=dict(color="white", size=13)),
        dragmode=False,
    )
    figure.update_xaxes(showgrid=True, gridcolor="#e2e8f0", zeroline=False, fixedrange=True)
    figure.update_yaxes(showgrid=False, fixedrange=True)
    figure.update_layout(**layout)
    charts.append(
        {
            "id": chart_id,
            "title": title,
            "description": description,
            "figure": json.loads(figure.to_json()),
        }
    )
    return (
        f'<article class="comparison-chart-card"><h3 id="{chart_id}-title">{escape(title)}</h3>'
        f'<p id="{chart_id}-description">{escape(description)}</p>'
        f'<div id="{chart_id}" class="comparison-chart" style="height:{height}px" role="img" '
        f'aria-labelledby="{chart_id}-title" aria-describedby="{chart_id}-description"></div></article>'
    )


def horizontal_bar(values, *, colors=model_colors, text=None, customdata=None, hover=None):
    return go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=text,
        textposition="outside",
        cliponaxis=False,
        customdata=customdata or models,
        hovertemplate=hover or "%{customdata}<br>%{x:,.2f}<extra></extra>",
    )


# Report only what the service returned; MAI output remains an unsplit total.
tokens = go.Figure()
for field, name, color in [
    ("input_text", "Input text", "#2563eb"),
    ("input_image", "Input image", "#38bdf8"),
    ("output_tokens", "Output total", "#0f766e"),
]:
    tokens.add_bar(
        y=labels,
        x=usage[field].tolist(),
        orientation="h",
        name=name,
        marker_color=color,
        customdata=[[model, float(usage.loc[model, "total_tokens"])] for model in models],
        hovertemplate="%{customdata[0]}<br>"
        + name
        + ": %{x:,.2f} tokens<br>Total: %{customdata[1]:,.2f} tokens<extra></extra>",
    )
usage_charts = chart(
    tokens,
    "usage-token-chart",
    "Average tokens per image",
    "Input text + input image + output total. MAI output is not split into text and image tokens.",
    barmode="stack",
    xaxis=dict(title="Tokens per successful image", rangemode="tozero"),
    yaxis=dict(autorange="reversed"),
)
latencies = usage.elapsed_seconds.tolist()
usage_charts += chart(
    go.Figure(
        horizontal_bar(
            latencies,
            text=[f"{v:.2f} s" for v in latencies],
            hover="%{customdata}<br>Average: %{x:.2f} seconds<extra></extra>",
        )
    ),
    "usage-latency-chart",
    "Average response time",
    "Five successful requests per model. GPT low quality and MAI defaults differ; these are observed sample averages.",
    xaxis=dict(title="Seconds per successful image", range=[0, max(latencies) * 1.24]),
    yaxis=dict(autorange="reversed"),
    showlegend=False,
)

rates = go.Figure()
for field, name, color in [
    ("input_text", "Input text", "#2563eb"),
    ("input_image", "Input image", "#38bdf8"),
    ("output_text", "Output text", "#f59e0b"),
    ("output_image", "Output image", "#0f766e"),
]:
    rates.add_bar(
        y=labels,
        x=[pricing["usd_per_million_tokens"][m][field] for m in models],
        name=name,
        orientation="h",
        marker_color=color,
        customdata=models,
        hovertemplate="%{customdata}<br>" + name + ": $%{x:.2f} per 1M tokens<extra></extra>",
    )
rate_chart = chart(
    rates,
    "token-rate-chart",
    "Token rates by modality",
    "Missing rates have no bar. GPT uses public reference rates; both MAI models use the supplied $5 text-input / $33 image-output starting rates.",
    height=520,
    barmode="group",
    bargap=0.24,
    xaxis=dict(title="USD per one million tokens", tickprefix="$", rangemode="tozero"),
    yaxis=dict(autorange="reversed"),
)

quality_section = re.search(r'<section id="quality-pricing">(.*?)</section>', html, re.S).group(1)
quality_body = re.search(r"<tbody>(.*?)</tbody>", quality_section, re.S).group(1)
quality_rows = [
    [
        unescape(re.sub(r"<[^>]+>", "", value)).strip()
        for value in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
    ]
    for row in re.findall(r"<tr>(.*?)</tr>", quality_body, re.S)
]
quality = go.Figure()
for index, label, color in [(1, "1024 × 1024", "#2563eb"), (2, "1536 × 1024", "#0f766e")]:
    quality.add_scatter(
        x=[r[0] for r in quality_rows],
        y=[float(r[index].replace("$", "")) for r in quality_rows],
        name=label,
        mode="lines+markers",
        line=dict(color=color, width=3),
        marker_size=9,
        hovertemplate=label + "<br>%{x}: $%{y:.5f}<extra></extra>",
    )
quality_chart = chart(
    quality,
    "quality-price-chart",
    "Supplied cost by quality level",
    "Apidog values supplied by the user. The applicable model and pricing basis are unspecified; these are not applied to MAI.",
    margin=dict(l=75, r=30, t=55, b=65),
    xaxis=dict(title="Quality", type="category"),
    yaxis=dict(
        title="USD per image",
        tickprefix="$",
        rangemode="tozero",
        showgrid=True,
        gridcolor="#e2e8f0",
    ),
)

averages = summary.reindex(models).average_priced_prompt_usd.tolist()
coverage = [
    [m, int(summary.loc[m, "priced_prompts"]), int(summary.loc[m, "prompts"])] for m in models
]
cost_charts = chart(
    go.Figure(
        horizontal_bar(
            averages,
            text=[f"${v:.5f}" for v in averages],
            customdata=coverage,
            hover="%{customdata[0]}<br>$%{x:.6f} per priced prompt<br>%{customdata[1]} of %{customdata[2]} prompts priced<extra></extra>",
        )
    ),
    "average-cost-chart",
    "Average fully priced prompt",
    "Coverage differs: GPT includes 5/5 prompts; MAI includes 4/5 and excludes portrait edits. These averages use different prompt mixes.",
    xaxis=dict(title="USD per priced prompt", tickprefix="$", range=[0, max(averages) * 1.28]),
    yaxis=dict(autorange="reversed"),
    showlegend=False,
)
projections = [
    None if pd.isna(v) else float(v) for v in summary.reindex(models).projected_workload_usd
]
projection = go.Figure(
    horizontal_bar(
        projections,
        text=[f"${v:.2f}" if v is not None else "" for v in projections],
        hover="%{customdata}<br>1,000 images: $%{x:.4f}<extra></extra>",
    )
)
for label, value in zip(labels, projections):
    if value is None:
        projection.add_annotation(
            x=0.15,
            y=label,
            text="N/A: image-input rate",
            xanchor="left",
            showarrow=False,
            font=dict(color="#92400e", size=11),
        )
cost_charts += chart(
    projection,
    "workload-cost-chart",
    "Projected cost for 1,000 images",
    "Same five-prompt mix with equal weights. MAI full-workload costs remain unavailable, not zero.",
    xaxis=dict(
        title="USD for 1,000 images",
        tickprefix="$",
        range=[0, max(v for v in projections if v is not None) * 1.28],
    ),
    yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=labels),
    showlegend=False,
)

scenario_names = {
    "product": "Product photo",
    "poster": "Poster / typography",
    "illustration": "Illustration",
    "portrait_astronaut": "Portrait edit",
    "transparent_mascot": "Mascot",
}
z, hover, text = [], [], []
for scenario, title in scenario_names.items():
    z_row, hover_row, text_row = [], [], []
    for model in models:
        row = prompts.loc[prompts.scenario.eq(scenario) & prompts.model.eq(model)].iloc[0]
        total = row.estimated_cost_usd
        z_row.append(None if pd.isna(total) else float(total))
        hover_row.append(
            f"{model}<br>{title}<br>Complete estimate: ${total:.6f}"
            if pd.notna(total)
            else "Total unavailable"
        )
        text_row.append(
            f"${total:.6f}"
            if pd.notna(total)
            else f"Total N/A<br>Subtotal<br>${row.known_component_cost_usd:.6f}"
        )
    z.append(z_row)
    hover.append(hover_row)
    text.append(text_row)
heatmap = go.Figure(
    go.Heatmap(
        z=z,
        x=labels,
        y=list(scenario_names.values()),
        colorscale=[[0, "#eff6ff"], [1, "#1d4ed8"]],
        zmin=0,
        customdata=hover,
        hovertemplate="%{customdata}<extra></extra>",
        hoverongaps=False,
        colorbar=dict(title="USD", tickprefix="$", thickness=12),
        xgap=3,
        ygap=3,
    )
)
for yi, title in enumerate(scenario_names.values()):
    for xi, label in enumerate(labels):
        value = z[yi][xi]
        heatmap.add_annotation(
            x=label,
            y=title,
            text=text[yi][xi],
            showarrow=False,
            font=dict(size=11, color="white" if value is not None and value > 0.022 else "#334155"),
        )
heatmap_chart = chart(
    heatmap,
    "prompt-cost-chart",
    "Cost by prompt and model",
    "Colored cells are complete estimates. MAI portrait cells have no cost color: $0.034374 is only the text/output subtotal, plus unpriced image input.",
    height=430,
    margin=dict(l=145, r=55, t=20, b=80),
    xaxis=dict(side="bottom", tickangle=-15),
    yaxis=dict(autorange="reversed"),
)


# Optional independent Flare quality experiment; it does not alter six-model averages.
flare_charts = ""
flare_metrics = GALLERY / "flare-quality/metrics.json"
if flare_metrics.is_file() and 'id="flare-quality"' in html:
    measured = json.loads(flare_metrics.read_text())["results"]
    levels = [row["quality"] for row in measured]
    costs = [row["estimated_cost_usd"] for row in measured]
    seconds = [row["elapsed_seconds"] for row in measured]
    cost_line = go.Figure(
        go.Scatter(
            x=levels,
            y=costs,
            mode="lines+markers",
            line=dict(color="#2563eb", width=3),
            marker_size=10,
            customdata=[[r["input_text"], r["output_image"]] for r in measured],
            hovertemplate="%{x}<br>Total estimate: $%{y:.6f}<br>Input text: %{customdata[0]} tokens<br>Image output: %{customdata[1]} tokens<extra></extra>",
        )
    )
    flare_charts += chart(
        cost_line,
        "flare-quality-cost-chart",
        "Flare estimated cost by quality",
        "Same prompt and 1024 × 1024 PNG output. Each estimate includes text-input and image-output tokens.",
        margin=dict(l=75, r=30, t=25, b=65),
        showlegend=False,
        xaxis=dict(title="Quality", type="category"),
        yaxis=dict(
            title="Estimated USD per image",
            tickprefix="$",
            rangemode="tozero",
            showgrid=True,
            gridcolor="#e2e8f0",
        ),
    )
    timing = go.Figure(
        go.Bar(
            x=levels,
            y=seconds,
            marker_color=["#93c5fd", "#60a5fa", "#3b82f6", "#1d4ed8"],
            text=[f"{value:.2f} s" for value in seconds],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>Observed latency: %{y:.2f} seconds<extra></extra>",
        )
    )
    flare_charts += chart(
        timing,
        "flare-quality-latency-chart",
        "Flare response time by quality",
        "One successful call per level, including network and authentication time; this is not a latency benchmark.",
        margin=dict(l=75, r=30, t=25, b=65),
        showlegend=False,
        xaxis=dict(title="Quality"),
        yaxis=dict(
            title="Seconds", range=[0, max(seconds) * 1.2], showgrid=True, gridcolor="#e2e8f0"
        ),
    )


def insert_charts(section_id, content, *, before_heading=None):
    global html
    match = re.search(rf'<section id="{section_id}">.*?</section>', html, re.S)
    if not match:
        raise ValueError(f"Missing section: {section_id}")
    section = match.group()
    marker = f"charts-{section_id}"
    section = re.sub(rf"<!-- {marker}:start -->.*?<!-- {marker}:end -->", "", section, flags=re.S)
    block = f'<!-- {marker}:start --><div class="comparison-charts">{content}</div><!-- {marker}:end -->'
    if before_heading:
        section = section.replace(before_heading, block + before_heading, 1)
    else:
        section = section.removesuffix("</section>") + block + "</section>"
    html = html[: match.start()] + section + html[match.end() :]


if flare_charts:
    insert_charts("flare-quality", flare_charts)
insert_charts("observed-usage", usage_charts)
insert_charts("pricing", rate_chart)
insert_charts("quality-pricing", quality_chart)
insert_charts(
    "estimated-costs",
    cost_charts + '<div class="comparison-chart-wide">' + heatmap_chart + "</div>",
)
styles = """<style id="comparison-chart-styles">
.comparison-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:24px 0}
.comparison-charts>.comparison-chart-card:only-child,.comparison-chart-wide{grid-column:1/-1}
.comparison-chart-card{min-width:0;border:1px solid #dbe3ee;border-radius:12px;background:#fff;padding:18px 12px 8px;overflow:hidden}
.comparison-chart-card h3{font-size:19px;margin:0 8px 8px;color:#0f172a}
.comparison-chart-card p{font-size:14px;line-height:1.5;margin:0 8px 12px;color:#475569;min-height:42px}
.comparison-chart{width:100%;min-height:420px}.comparison-chart-wide{min-width:0}
.comparison-chart-wide .comparison-chart-card{overflow-x:auto}.comparison-chart-wide .comparison-chart{min-width:860px}
.comparison-chart-note{font-size:14px;color:#475569}
@media(max-width:1050px){.comparison-charts{grid-template-columns:minmax(0,1fr)}.comparison-chart-card{padding:14px 4px 4px}}
@media print{.modebar{display:none!important}.comparison-chart-card{break-inside:avoid}}
</style>"""
html = re.sub(r'<style id="comparison-chart-styles">.*?</style>', "", html, flags=re.S)
html = html.replace("<h1>", styles + "<h1>", 1)
html = re.sub(
    r"<!-- comparison-chart-runtime:start -->.*?<!-- comparison-chart-runtime:end -->",
    "",
    html,
    flags=re.S,
)
payload = json.dumps(charts, ensure_ascii=True, allow_nan=False).replace("</", "<\\/")
runtime = (
    """<!-- comparison-chart-runtime:start -->
<script src="plotly.min.js"></script>
<script id="comparison-chart-data" type="application/json">"""
    + payload
    + """</script>
<script>
const comparisonCharts = JSON.parse(document.getElementById('comparison-chart-data').textContent);
window.comparisonChartsReady = Promise.all(comparisonCharts.map(chart => Plotly.newPlot(
  chart.id, chart.figure.data, chart.figure.layout,
  {responsive:true, displaylogo:false, displayModeBar:true, modeBarButtons:[['toImage']],
   toImageButtonOptions:{format:'png',filename:chart.id,scale:2}}
)));
</script>
<!-- comparison-chart-runtime:end -->"""
)
html = html.replace("</html>", runtime + "</html>")
# One local Plotly bundle serves every graph and supports opening index.html offline.
(GALLERY / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
(GALLERY / "comparison-charts.json").write_text(
    json.dumps(charts, indent=2, allow_nan=False) + "\n", encoding="utf-8"
)
PAGE.write_text(html, encoding="utf-8")
print(f"Updated {len(charts)} offline charts: {PAGE}")
