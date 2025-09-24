"""Utility to compare deployed vs reserved Provisioned Throughput Units (PTUs).

The tool calls Azure management REST APIs for Cognitive Services deployments and
Reservations to determine how much throughput is deployed versus what has been
reserved. It is meant to be executed with credentials that can access both
resources (for example, via environment variables consumed by
``DefaultAzureCredential``).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import requests
from azure.identity import DefaultAzureCredential, AzureError

MANAGEMENT_SCOPE = "https://management.azure.com/.default"
DEPLOYMENTS_API_VERSION = "2024-04-01-preview"
RESERVATIONS_API_VERSION = "2022-11-01"

logger = logging.getLogger(__name__)


class AzureManagementClient:
    """Lightweight wrapper around requests that injects AAD tokens."""

    def __init__(self, credential: Optional[DefaultAzureCredential] = None) -> None:
        self.credential = credential or DefaultAzureCredential(
            exclude_interactive_browser_credential=False
        )
        self.session = requests.Session()
        self._cached_token: Optional[str] = None
        self._expiry: float = 0.0

    def _get_token(self) -> str:
        now = time.time()
        if self._cached_token and now < (self._expiry - 60):
            return self._cached_token
        access_token = self.credential.get_token(MANAGEMENT_SCOPE)
        self._cached_token = access_token.token
        self._expiry = float(access_token.expires_on)
        return self._cached_token

    def get(self, url: str, params: Optional[Dict[str, str]] = None) -> Dict:
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }
        response = self.session.get(url, params=params, headers=headers, timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Request to {url} failed with status {response.status_code}: {response.text}"
            )
        return response.json()

    def paged_get(self, url: str, params: Optional[Dict[str, str]] = None) -> Iterable[Dict]:
        next_url = url
        next_params = dict(params or {})
        while next_url:
            payload = self.get(next_url, params=next_params)
            for item in payload.get("value", []):
                yield item
            next_url = payload.get("nextLink")
            # Only include params on the initial request; nextLink already contains them.
            next_params = None


@dataclass
class DeploymentThroughput:
    name: str
    sku_name: str
    capacity: float


@dataclass
class ReservationThroughput:
    reservation_id: str
    sku_name: str
    quantity: float
    resource_type: str


def load_deployments(
    client: AzureManagementClient,
    subscription_id: str,
    resource_group: str,
    account_name: str,
    api_version: str = DEPLOYMENTS_API_VERSION,
) -> List[DeploymentThroughput]:
    base_url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/deployments"
    )
    deployments: List[DeploymentThroughput] = []
    for item in client.paged_get(base_url, {"api-version": api_version}):
        sku = item.get("sku", {}) or {}
        properties = item.get("properties", {}) or {}
        capacity = sku.get("capacity") or properties.get("currentCapacity")
        if capacity is None:
            logger.warning("Deployment %s does not expose a capacity value", item.get("name"))
            continue
        deployments.append(
            DeploymentThroughput(
                name=item.get("name", ""),
                sku_name=sku.get("name", "Unknown"),
                capacity=float(capacity),
            )
        )
    return deployments


def load_reservations(
    client: AzureManagementClient,
    api_version: str = RESERVATIONS_API_VERSION,
    reserved_resource_type: Optional[str] = None,
    state_filter: Optional[str] = None,
) -> List[ReservationThroughput]:
    base_url = "https://management.azure.com/providers/Microsoft.Capacity/reservations"
    params: Dict[str, str] = {"api-version": api_version}
    filters: List[str] = []
    if reserved_resource_type:
        filters.append(f"properties/reservedResourceType eq '{reserved_resource_type}'")
    if state_filter:
        filters.append(f"properties/provisioningState eq '{state_filter}'")
    if filters:
        params["$filter"] = " and ".join(filters)

    reservations: List[ReservationThroughput] = []
    for item in client.paged_get(base_url, params):
        properties = item.get("properties", {}) or {}
        sku = item.get("sku", {}) or {}
        quantity = properties.get("quantity")
        resource_type = properties.get("reservedResourceType", "")
        if quantity is None:
            logger.warning("Reservation %s has no quantity", item.get("id"))
            continue
        reservations.append(
            ReservationThroughput(
                reservation_id=item.get("id", ""),
                sku_name=sku.get("name", "Unknown"),
                quantity=float(quantity),
                resource_type=resource_type,
            )
        )
    return reservations


def aggregate_by_sku(values: Iterable) -> Dict[str, float]:
    totals: Dict[str, float] = defaultdict(float)
    for value in values:
        sku = getattr(value, "sku_name", "Unknown")
        totals[sku] += getattr(value, "capacity", getattr(value, "quantity", 0.0))
    return dict(sorted(totals.items()))


def compare_throughput(
    deployments: List[DeploymentThroughput], reservations: List[ReservationThroughput]
) -> Dict[str, Dict[str, float]]:
    deployed_totals = aggregate_by_sku(deployments)
    reserved_totals = aggregate_by_sku(reservations)
    all_skus = set(deployed_totals) | set(reserved_totals)
    comparison: Dict[str, Dict[str, float]] = {}
    for sku in sorted(all_skus):
        deployed = deployed_totals.get(sku, 0.0)
        reserved = reserved_totals.get(sku, 0.0)
        comparison[sku] = {
            "deployed": deployed,
            "reserved": reserved,
            "delta": reserved - deployed,
        }
    return comparison


def format_table(comparison: Dict[str, Dict[str, float]]) -> str:
    if not comparison:
        return "No throughput data found."
    lines = [f"{'SKU':<30} {'Deployed':>12} {'Reserved':>12} {'Delta':>12}", "-" * 70]
    for sku, values in comparison.items():
        lines.append(
            f"{sku:<30} {values['deployed']:>12.2f} {values['reserved']:>12.2f} {values['delta']:>12.2f}"
        )
    totals = {
        "deployed": sum(v["deployed"] for v in comparison.values()),
        "reserved": sum(v["reserved"] for v in comparison.values()),
    }
    totals["delta"] = totals["reserved"] - totals["deployed"]
    lines.append("-" * 70)
    lines.append(
        f"{'TOTAL':<30} {totals['deployed']:>12.2f} {totals['reserved']:>12.2f} {totals['delta']:>12.2f}"
    )
    return "\n".join(lines)


def comparison_rows(comparison: Dict[str, Dict[str, float]]) -> List[Dict[str, float]]:
    return [
        {
            "sku": sku,
            "deployed": values.get("deployed", 0.0),
            "reserved": values.get("reserved", 0.0),
            "delta": values.get("delta", 0.0),
        }
        for sku, values in comparison.items()
    ]


def comparison_totals(comparison: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    deployed = sum(values.get("deployed", 0.0) for values in comparison.values())
    reserved = sum(values.get("reserved", 0.0) for values in comparison.values())
    return {
        "deployed": deployed,
        "reserved": reserved,
        "delta": reserved - deployed,
    }


def format_csv(comparison: Dict[str, Dict[str, float]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "deployed", "reserved", "delta"])
    for row in comparison_rows(comparison):
        writer.writerow(
            [row["sku"], f"{row['deployed']:.2f}", f"{row['reserved']:.2f}", f"{row['delta']:.2f}"]
        )
    totals = comparison_totals(comparison)
    writer.writerow(
        [
            "TOTAL",
            f"{totals['deployed']:.2f}",
            f"{totals['reserved']:.2f}",
            f"{totals['delta']:.2f}",
        ]
    )
    return output.getvalue()


def format_json(comparison: Dict[str, Dict[str, float]]) -> str:
    payload = {
        "items": comparison_rows(comparison),
        "totals": comparison_totals(comparison),
    }
    return json.dumps(payload, indent=2)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare deployed provisioned throughput units (PTUs) for Azure AI "
            "Service deployments against reserved PTUs."
        )
    )
    parser.add_argument("subscription_id", help="Subscription ID that owns the deployments")
    parser.add_argument("resource_group", help="Resource group that hosts the account")
    parser.add_argument("account_name", help="Cognitive Services account name")
    parser.add_argument(
        "--reserved-resource-type",
        default="OpenAIPTU",
        help="Filter reservations by reserved resource type (default: OpenAIPTU)",
    )
    parser.add_argument(
        "--deployment-api-version",
        default=DEPLOYMENTS_API_VERSION,
        help="API version for deployments endpoint",
    )
    parser.add_argument(
        "--reservation-api-version",
        default=RESERVATIONS_API_VERSION,
        help="API version for reservations endpoint",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--include-reservation-state",
        help="Optionally filter reservations by provisioning state (e.g. Succeeded)",
    )
    parser.add_argument(
        "--output-format",
        default="table",
        choices=["table", "csv", "json"],
        help="Output format for the comparison (default: table)",
    )
    parser.add_argument(
        "--output-file",
        help="Optional file path to write the comparison output",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    try:
        client = AzureManagementClient()
    except AzureError as exc:  # pragma: no cover - depends on runtime auth
        logger.error("Failed to initialize Azure credential: %s", exc)
        return 1

    try:
        deployments = load_deployments(
            client,
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            account_name=args.account_name,
            api_version=args.deployment_api_version,
        )
        reservations = load_reservations(
            client,
            api_version=args.reservation_api_version,
            reserved_resource_type=args.reserved_resource_type,
            state_filter=args.include_reservation_state,
        )
    except RuntimeError as exc:
        logger.error("Failed to query Azure management API: %s", exc)
        return 1

    comparison = compare_throughput(deployments, reservations)
    if args.output_format == "csv":
        output = format_csv(comparison)
    elif args.output_format == "json":
        output = format_json(comparison)
    else:
        output = format_table(comparison)

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as file_handle:
            file_handle.write(output)
    else:
        print(output)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
