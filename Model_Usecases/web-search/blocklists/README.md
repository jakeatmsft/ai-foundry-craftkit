# Azure OpenAI Domain Blocklist

This folder is intentionally minimal:

- `domains.txt`: newline-delimited domain and IP blocklist entries.
- `upload_blocklist_manifest.py`: standard-library Python uploader that reads `domains.txt` directly and creates Azure OpenAI RAI blocklists with the Batch Add API.

No manifest build step, PowerShell wrapper, test fixture, or generated output is kept here.

## Prerequisites

- Python 3.10+
- Azure CLI installed
- An active Azure CLI session via `az login`

## Usage

From this directory:

```bash
python upload_blocklist_manifest.py \
  --subscription-id <subscription-id> \
  --resource-group-name <resource-group> \
  --account-name <foundry-or-azure-openai-resource-name> \
  --blocklist-base-name jpmc-domain-blacklist-2025-08-26 \
  --description "Domains from domains.txt" \
  --match-mode exact
```

Optional arguments:

- `--domains-path`: defaults to `./domains.txt`
- `--batch-size`: defaults to `100`
- `--max-items-per-list`: defaults to `10000`
- `--match-mode regex-domain`: turns domain entries into regex patterns that also match subdomains; IP entries remain exact

## Notes

- The script follows the same Azure management API upload flow as the previous manifest uploader, but it builds the blocklist items in memory from `domains.txt`.
- If the input exceeds Azure's per-blocklist item limit, the script automatically splits it into `...-001`, `...-002`, and so on.
- Re-running against an existing blocklist uses the same create-if-missing and batch-upload behavior as the prior uploader.
