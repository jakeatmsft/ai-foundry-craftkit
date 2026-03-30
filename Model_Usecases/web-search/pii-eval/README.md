# PII Web Search Eval

This eval set stress-tests web search tool-call hygiene for a regional-bank wealth advisor scenario.

## Files

- `data/search_eval_pii.jsonl`: prompts that require web search and include synthetic personal data.
- `data/seed_prompt.json`: system prompt configured for a regional-bank wealth advisor with explicit PII suppression requirements.
- `generate_eval_dataset.py`: sends each prompt to the Responses API and stores raw payloads.
- `tests/test_tool_call_pii_redaction.py`: extracts all tool-call records and fails if any personal data appears in tool-call payload metadata.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r pii-eval/requirements.txt
python pii-eval/generate_eval_dataset.py
pytest -q pii-eval/tests/test_tool_call_pii_redaction.py
```

Optional: point the test at a specific raw output file.

```bash
PII_EVAL_OUTPUT=pii-eval/outputs/pii_eval_raw_YYYYMMDD_HHMMSS.jsonl pytest -q pii-eval/tests/test_tool_call_pii_redaction.py
```
