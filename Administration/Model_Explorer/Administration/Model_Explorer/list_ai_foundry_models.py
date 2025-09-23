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


def format_table(models: List[Dict[str, Any]]) -> str:
    rows: List[List[str]] = []
    headers = ["Provider", "Model Name", "Version", "SKU", "Format", "MaxCapacity"]
    rows.append(headers)
    for m in models:
        model = m.get("model", {}) or {}
        rows.append([
            str(m.get("kind", "")),
            str(model.get("name", "")),
            str(model.get("version", "")),
            str(m.get("skuName", "")),
            str(model.get("format", "")),
            str(model.get("maxCapacity", "")),
        ])

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for ridx, row in enumerate(rows):
        line = "  ".join(val.ljust(widths[i]) for i, val in enumerate(row))
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
        print(format_table(models))
    else:
        print(f"No models found in {args.location}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
