#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except Exception:
    DefaultAzureCredential = None  # type: ignore

import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

MANAGEMENT_SCOPE = "https://management.azure.com/.default"
MANAGEMENT_RESOURCE = "https://management.azure.com"


def stderr(msg: str) -> None:
    sys.stderr.write(msg + "\n")


def get_env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    return fallback


def get_management_token(verbose: bool = False) -> str:
    token = os.environ.get("AZURE_ACCESS_TOKEN") or os.environ.get("ARM_ACCESS_TOKEN")
    if token:
        if verbose:
            stderr("Using token from environment variable AZURE_ACCESS_TOKEN/ARM_ACCESS_TOKEN")
        return token

    if DefaultAzureCredential is not None:
        try:
            cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
            access_token = cred.get_token(MANAGEMENT_SCOPE)
            if verbose:
                stderr("Using token from azure-identity DefaultAzureCredential")
            return access_token.token
        except Exception as e:
            if verbose:
                stderr(f"DefaultAzureCredential failed: {e}")

    try:
        import subprocess
        cmd = [
            "az",
            "account",
            "get-access-token",
            "--resource",
            MANAGEMENT_RESOURCE,
            "--output",
            "json",
        ]
        if verbose:
            stderr("Attempting to obtain token via Azure CLI (az)")
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        token = data.get("accessToken") or data.get("access_token")
        if not token:
            raise RuntimeError("Azure CLI did not return access token")
        if verbose:
            stderr("Using token from Azure CLI")
        return token
    except Exception:
        pass

    raise RuntimeError(
        "Unable to acquire Azure management access token. Provide AZURE_ACCESS_TOKEN, "
        "authenticate via azure-identity (Environment/Managed Identity/CLI), or ensure Azure CLI is installed."
    )


def http_get(url: str, token: str, verbose: bool = False) -> Tuple[int, Dict[str, Any]]:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        if verbose:
            stderr(f"GET {url}")
        with urllib.request.urlopen(req) as resp:
            status = resp.getcode()
            body = resp.read()
            data = json.loads(body) if body else {}
            return status, data
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {"error": body.decode("utf-8", errors="ignore")}
        return e.code, data


def list_models(subscription_id: str, location: str, api_version: str, token: str, verbose: bool = False) -> List[Dict[str, Any]]:
    base = (
        f"{MANAGEMENT_RESOURCE}/subscriptions/{subscription_id}/providers/Microsoft.CognitiveServices/"
        f"locations/{location}/models?api-version={api_version}"
    )
    all_items: List[Dict[str, Any]] = []
    url = base
    while url:
        status, data = http_get(url, token, verbose=verbose)
        if status != 200:
            raise RuntimeError(f"Request failed with status {status}: {json.dumps(data, indent=2)}")
        items = data.get("value") or []
        if isinstance(items, list):
            all_items.extend(items)
        next_link = data.get("nextLink") or data.get("next_link")
        if next_link:
            url = next_link
            continue
        break
    return all_items


def unique_providers(models: Iterable[Dict[str, Any]]) -> List[str]:
    kinds = []
    seen = set()
    for m in models:
        k = m.get("kind")
        if k and k not in seen:
            seen.add(k)
            kinds.append(k)
    kinds.sort()
    return kinds


def flatten_model(m: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a model entry to include all nested fields with prefixes."""
    flat: Dict[str, Any] = {}
    
    # Top-level fields
    for key, val in m.items():
        if key == "model" and isinstance(val, dict):
            # Flatten nested model dict with 'model.' prefix
            for mk, mv in val.items():
                if mk == "capabilities" and isinstance(mv, dict):
                    # Flatten capabilities with 'capabilities.' prefix
                    for ck, cv in mv.items():
                        flat[f"capabilities.{ck}"] = cv
                elif mk == "deprecation" and isinstance(mv, dict):
                    # Flatten deprecation with 'deprecation.' prefix
                    for dk, dv in mv.items():
                        flat[f"deprecation.{dk}"] = dv
                elif mk == "skus" and isinstance(mv, list):
                    # Join SKU info
                    flat["model.skus"] = ", ".join(
                        f"{s.get('name', '')}(cap:{s.get('capacity', {}).get('maximum', '')})" 
                        for s in mv if isinstance(s, dict)
                    )
                elif mk == "finetune" and isinstance(mv, dict):
                    # Flatten finetune with 'finetune.' prefix
                    for fk, fv in mv.items():
                        flat[f"finetune.{fk}"] = fv
                elif mk == "systemData" and isinstance(mv, dict):
                    # Flatten systemData
                    for sk, sv in mv.items():
                        flat[f"systemData.{sk}"] = sv
                elif mk == "lifecycleStatus" and isinstance(mv, dict):
                    # Flatten lifecycleStatus
                    for lk, lv in mv.items():
                        flat[f"lifecycleStatus.{lk}"] = lv
                else:
                    flat[f"model.{mk}"] = mv
        elif isinstance(val, dict):
            # Flatten other nested dicts
            for nk, nv in val.items():
                flat[f"{key}.{nk}"] = nv
        elif isinstance(val, list):
            flat[key] = json.dumps(val) if val else ""
        else:
            flat[key] = val
    
    return flat


def get_catalog_url(model_name: str) -> str:
    """Construct the Azure AI catalog URL for a model."""
    if not model_name:
        return ""
    return f"https://ai.azure.com/explore/models/{model_name}"


def format_table(models: List[Dict[str, Any]]) -> str:
    rows: List[List[str]] = []
    headers = ["Provider", "Model Name", "Version", "SKU", "Format", "MaxCapacity", "Catalog URL"]
    rows.append(headers)
    for m in models:
        model = m.get("model", {}) or {}
        model_name = str(model.get("name", ""))
        rows.append([
            str(m.get("kind", "")),
            model_name,
            str(model.get("version", "")),
            str(m.get("skuName", "")),
            str(model.get("format", "")),
            str(model.get("maxCapacity", "")),
            get_catalog_url(model_name),
        ])

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for ridx, row in enumerate(rows):
        line = "  ".join(val.ljust(widths[i]) for i, val in enumerate(row))
        lines.append(line)
        if ridx == 0:
            lines.append("  ".join("-" * widths[i] for i in range(len(widths))))
    return "\n".join(lines)


def format_full_table(models: List[Dict[str, Any]]) -> str:
    """Format a table with all available fields from the API response."""
    if not models:
        return ""
    
    # Flatten all models and collect all unique keys
    flat_models = [flatten_model(m) for m in models]
    all_keys: List[str] = []
    seen_keys: set = set()
    
    # Add catalog URL to each flattened model
    for fm in flat_models:
        model_name = fm.get("model.name", "")
        fm["catalogUrl"] = get_catalog_url(model_name) if model_name else ""
    
    # Define preferred column order for readability
    priority_keys = [
        "kind", "skuName", "model.name", "model.version", "model.format", 
        "model.maxCapacity", "catalogUrl", "model.source", "model.isDefaultVersion",
        "capabilities.completion", "capabilities.chatCompletion", "capabilities.embeddings",
        "capabilities.imageGeneration", "capabilities.fineTune", "capabilities.inference",
        "deprecation.fineTune", "deprecation.inference",
        "lifecycleStatus.status",
        "model.skus"
    ]
    
    # Add priority keys first if they exist
    for k in priority_keys:
        for fm in flat_models:
            if k in fm and k not in seen_keys:
                all_keys.append(k)
                seen_keys.add(k)
                break
    
    # Add remaining keys
    for fm in flat_models:
        for k in fm.keys():
            if k not in seen_keys:
                all_keys.append(k)
                seen_keys.add(k)
    
    # Build rows
    rows: List[List[str]] = []
    rows.append(all_keys)
    
    for fm in flat_models:
        row = []
        for k in all_keys:
            val = fm.get(k, "")
            if val is None:
                val = ""
            elif isinstance(val, bool):
                val = "true" if val else "false"
            else:
                val = str(val)
            row.append(val)
        rows.append(row)
    
    # Calculate column widths
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(all_keys))]
    
    # Build output
    lines = []
    for ridx, row in enumerate(rows):
        line = "  ".join(str(val).ljust(widths[i]) for i, val in enumerate(row))
        lines.append(line)
        if ridx == 0:
            lines.append("  ".join("-" * widths[i] for i in range(len(widths))))
    
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="List AI Foundry Models and Providers (Azure Management API)")
    parser.add_argument("--subscription-id", "-s", default=get_env("AZURE_SUBSCRIPTION_ID", get_env("AZURE_SUBSCRIPTION_ID")), help="Azure subscription ID (env: AZURE_SUBSCRIPTION_ID)")
    parser.add_argument("--location", "-l", required=False, default=get_env("AZURE_LOCATION", get_env("LOCATION")), help="Azure location, e.g. westus, eastus, WestUS")
    parser.add_argument("--api-version", default="2025-06-01", help="API version for the request (default: 2025-06-01)")
    parser.add_argument("--output", "-o", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--full", "-f", action="store_true", help="Show all available fields from the API response")
    parser.add_argument("--providers-only", action="store_true", help="Only print unique providers")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if not args.subscription_id:
        stderr("--subscription-id is required (or set AZURE_SUBSCRIPTION_ID)")
        return 2
    if not args.location:
        stderr("--location is required (or set AZURE_LOCATION)")
        return 2

    try:
        token = get_management_token(verbose=args.verbose)
    except Exception as e:
        stderr(str(e))
        return 1

    try:
        models = list_models(args.subscription_id, args.location, args.api_version, token, verbose=args.verbose)
    except Exception as e:
        stderr(f"Error listing models: {e}")
        return 1

    provs = unique_providers(models)

    if args.output == "json":
        out = {
            "subscriptionId": args.subscription_id,
            "location": args.location,
            "providers": provs,
            "models": models,
        }
        print(json.dumps(out, indent=2))
        return 0

    if args.providers_only:
        print("Providers:")
        for p in provs:
            print(f"- {p}")
        return 0

    print("Providers:")
    for p in provs:
        print(f"- {p}")
    print()
    if models:
        print(f"Models in {args.location} ({len(models)}):")
        if args.full:
            print(format_full_table(models))
        else:
            print(format_table(models))
    else:
        print(f"No models found in {args.location}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
