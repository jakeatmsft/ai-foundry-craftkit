#!/usr/bin/env python3
"""Upload Azure OpenAI RAI blocklists directly from a domains.txt file."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable
from urllib import error, request

CREATE_API_VERSION = "2024-04-01-preview"
BATCH_API_VERSION = "2024-10-01"
SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z._~-]+")
DOMAIN_BOUNDARY_RE = r"[^A-Za-z0-9-]"


def sanitize_name(name: str) -> str:
    sanitized = SAFE_NAME_RE.sub("-", name.strip()).strip("-")
    return sanitized or "blocklist"


def looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def build_pattern(value: str, match_mode: str) -> tuple[str, bool]:
    if match_mode == "exact" or looks_like_ip(value):
        return value, False

    escaped = re.escape(value)
    pattern = (
        rf"(?i)(?:^|{DOMAIN_BOUNDARY_RE})(?:[A-Za-z0-9-]+\.)*"
        rf"{escaped}(?:$|{DOMAIN_BOUNDARY_RE})"
    )
    return pattern, True


def load_domains(path: Path, match_mode: str) -> list[dict[str, Any]]:
    seen: set[tuple[bool, str]] = set()
    items: list[dict[str, Any]] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        value = raw_line.strip().lower()
        if not value or value.startswith("#"):
            continue

        pattern, is_regex = build_pattern(value, match_mode)
        dedupe_key = (is_regex, pattern)
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        items.append(
            {
                "domain": value,
                "pattern": pattern,
                "is_regex": is_regex,
            }
        )

    return items


def chunked(items: list[dict[str, Any]], chunk_size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


def get_access_token() -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token", "--query", "accessToken", "-o", "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Failed to acquire Azure access token from Azure CLI.")
    return token


def decode_response_body(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8")
    if not text.strip():
        return None
    return json.loads(text)


def arm_request(
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    max_attempts: int = 6,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"}
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    last_error: error.HTTPError | None = None
    for attempt in range(1, max_attempts + 1):
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=120) as response:
                return decode_response_body(response.read())
        except error.HTTPError as exc:
            if exc.code == 404 and method.upper() == "GET":
                return None

            last_error = exc
            if exc.code not in (408, 409, 429, 500, 502, 503, 504) or attempt == max_attempts:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"ARM request failed: {method.upper()} {url} returned {exc.code}: {detail}"
                ) from exc

            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = int(retry_after)
            else:
                delay = min(60, 2**attempt)
            time.sleep(delay)

    if last_error is not None:
        detail = last_error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ARM request failed after retries: {method.upper()} {url} returned "
            f"{last_error.code}: {detail}"
        ) from last_error

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload Azure OpenAI RAI blocklists directly from a domains.txt file."
    )
    parser.add_argument(
        "--domains-path",
        type=Path,
        default=Path(__file__).with_name("domains.txt"),
        help="Path to the newline-delimited domain/IP list.",
    )
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group-name", required=True)
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--blocklist-base-name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--match-mode",
        choices=("exact", "regex-domain"),
        default="exact",
        help="Use exact matches or regex hostname matches for subdomains.",
    )
    parser.add_argument(
        "--max-items-per-list",
        type=int,
        default=10_000,
        help="Azure item limit per blocklist before splitting into -001, -002, ...",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    return parser.parse_args()


def build_blocklists(
    items: list[dict[str, Any]],
    blocklist_base_name: str,
    description: str,
    max_items_per_list: int,
) -> list[dict[str, Any]]:
    safe_base_name = sanitize_name(blocklist_base_name)
    chunks = list(chunked(items, max_items_per_list))
    total_blocklists = len(chunks)
    blocklists: list[dict[str, Any]] = []

    for blocklist_index, chunk in enumerate(chunks, start=1):
        blocklist_name = (
            safe_base_name
            if total_blocklists == 1
            else f"{safe_base_name}-{blocklist_index:03d}"
        )
        blocklists.append(
            {
                "name": blocklist_name,
                "description": description,
                "items": chunk,
            }
        )

    return blocklists


def upload_blocklist(
    token: str,
    subscription_id: str,
    resource_group_name: str,
    account_name: str,
    blocklist: dict[str, Any],
    batch_size: int,
) -> None:
    blocklist_name = str(blocklist["name"])
    blocklist_url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group_name}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/raiBlocklists/"
        f"{blocklist_name}?api-version={CREATE_API_VERSION}"
    )

    blocklist_state = arm_request("GET", blocklist_url, token)
    if blocklist_state is None:
        print(f"Creating blocklist: {blocklist_name}", flush=True)
        arm_request(
            "PUT",
            blocklist_url,
            token,
            payload={"properties": {"description": blocklist["description"]}},
        )
    else:
        print(f"Blocklist already exists: {blocklist_name}", flush=True)

    batch_url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group_name}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/raiBlocklists/"
        f"{blocklist_name}/addRaiBlocklistItems?api-version={BATCH_API_VERSION}"
    )

    items = list(blocklist["items"])
    batches = list(chunked(items, batch_size))
    print(
        f"{blocklist_name}: uploading {len(items)} items in {len(batches)} batch request(s)",
        flush=True,
    )

    uploaded = 0
    for batch_number, batch in enumerate(batches, start=1):
        payload = [
            {
                "name": f"item-{item_index:05d}",
                "properties": {
                    "pattern": item["pattern"],
                    "isRegex": item["is_regex"],
                },
            }
            for item_index, item in enumerate(batch, start=uploaded + 1)
        ]
        arm_request("POST", batch_url, token, payload=payload)
        uploaded += len(batch)
        print(
            f"{blocklist_name}: uploaded {uploaded} / {len(items)} items "
            f"(batch {batch_number}/{len(batches)})",
            flush=True,
        )


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be greater than zero")
    if args.max_items_per_list <= 0:
        raise SystemExit("--max-items-per-list must be greater than zero")
    if not args.domains_path.is_file():
        raise SystemExit(f"Domains file not found: {args.domains_path}")

    items = load_domains(args.domains_path, args.match_mode)
    if not items:
        raise SystemExit(f"No domains found in {args.domains_path}")

    print(f"Loaded {len(items)} unique entries from {args.domains_path}", flush=True)
    token = get_access_token()
    blocklists = build_blocklists(
        items=items,
        blocklist_base_name=args.blocklist_base_name,
        description=args.description,
        max_items_per_list=args.max_items_per_list,
    )

    print(f"Preparing {len(blocklists)} blocklist(s)", flush=True)
    for blocklist in blocklists:
        upload_blocklist(
            token=token,
            subscription_id=args.subscription_id,
            resource_group_name=args.resource_group_name,
            account_name=args.account_name,
            blocklist=blocklist,
            batch_size=args.batch_size,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
