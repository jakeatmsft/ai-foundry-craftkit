#!/usr/bin/env bash
# Assigns Reader role to the provided principal across every reservation order in the tenant using Azure CLI.
# Usage: ./set_reservation_permissions.sh <tenant-id> <object-id>
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <tenant-id> <object-id>" >&2
  exit 1
fi

tenant_id="$1"
object_id="$2"

if ! command -v az >/dev/null 2>&1; then
  echo "Error: Azure CLI (az) is required to run this script." >&2
  exit 1
fi

# Ensure the user is authenticated for the requested tenant.
if ! az account show --query tenantId -o tsv --only-show-errors >/dev/null 2>&1; then
  echo "No active Azure CLI session detected. Initiating login for tenant $tenant_id..."
  az login --tenant "$tenant_id" --allow-no-subscriptions --use-device-code --only-show-errors --output none >/dev/null
fi

active_tenant="$(az account show --query tenantId -o tsv --only-show-errors 2>/dev/null || echo "")"
if [[ -z "$active_tenant" ]]; then
  echo "Error: Unable to determine active Azure CLI tenant. Ensure you have access to tenant $tenant_id." >&2
  exit 1
fi

if [[ "$active_tenant" != "$tenant_id" ]]; then
  echo "Warning: Active tenant ($active_tenant) does not match requested tenant ($tenant_id). Proceeding may yield incomplete results." >&2
fi

echo "Retrieving reservation order scopes from tenant $tenant_id..."
mapfile -t reservation_scopes < <(
  az reservations list --only-show-errors --query "[].id" -o tsv |
  sed 's#/reservations/.*##' |
  sort -u
)

if [[ ${#reservation_scopes[@]} -eq 0 ]]; then
  echo "No reservations found for the current Azure CLI context."
  exit 0
fi

echo "Found ${#reservation_scopes[@]} reservation order scope(s). Assigning Reader role to object $object_id..."
for scope in "${reservation_scopes[@]}"; do
  [[ -z "$scope" ]] && continue
  echo "Assigning Reader role at scope $scope"
  if az role assignment create --only-show-errors --assignee-object-id "$object_id" --role Reader --scope "$scope" --output none >/dev/null 2>&1; then
    echo "Successfully assigned Reader role at $scope"
  else
    echo "Warning: Failed to assign Reader role at $scope" >&2
  fi
done

echo "Completed processing role assignments."
