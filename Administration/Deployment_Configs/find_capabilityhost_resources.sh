#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Search for Azure Cognitive Services CapabilityHost resources.

Usage: find_capabilityhost_resources.sh [options]

Options:
  --subscription <name-or-id>   Limit search to a specific subscription. Repeat to search multiple subscriptions.
  --resource-group <name>       Limit search to a resource group.
  --tsv                         Output tab-separated values (default formats as a table if `column` is available).
  --no-header                   Omit the header row from output.
  -h, --help                    Show this help message.

The script enumerates account-level CapabilityHost resources
(Microsoft.CognitiveServices/accounts/capabilityHosts) and project-level
CapabilityHost resources (Microsoft.CognitiveServices/accounts/projects/capabilityHosts).

Requires the Azure CLI (`az`) to be installed and authenticated.
USAGE
}

if [[ $# -eq 1 && ( $1 == "-h" || $1 == "--help" ) ]]; then
  usage
  exit 0
fi

if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) is not installed or not on PATH." >&2
  exit 1
fi

subscriptions=()
resource_group=""
output_mode="table"
include_header=1

strip_cr() {
  local var_name="$1"
  local value=${!var_name-}
  value=${value//$'\r'/}
  printf -v "$var_name" '%s' "$value"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --subscription requires a value." >&2
        exit 1
      fi
      subscriptions+=("$2")
      shift 2
      ;;
    --resource-group)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --resource-group requires a value." >&2
        exit 1
      fi
      resource_group="$2"
      shift 2
      ;;
    --tsv)
      output_mode="tsv"
      shift
      ;;
    --no-header)
      include_header=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ${#subscriptions[@]} -eq 0 ]]; then
  mapfile -t subscriptions < <(az account list --query "[?state == 'Enabled'].id" -o tsv --only-show-errors)
  if [[ ${#subscriptions[@]} -eq 0 ]]; then
    echo "ERROR: No enabled subscriptions found. Use --subscription to specify one." >&2
    exit 1
  fi
fi

for i in "${!subscriptions[@]}"; do
  subscriptions[$i]="${subscriptions[$i]//$'\r'/}"
done

capability_host_api_version="2025-04-01-preview"

header="Subscription\tResourceType\tResourceGroup\tAccount\tProject\tCapabilityHost\tLocation\tProvisioningState"

lines=()
if (( include_header )); then
  lines+=("$header")
fi

found=0

collect_hosts_for_scope() {
  local subscription="$1"
  local scope_path="$2"
  local description="$3"

  local url="https://management.azure.com${scope_path}?api-version=${capability_host_api_version}"
  local output

  if ! output=$(az rest \
      --method get \
      --subscription "$subscription" \
      --url "$url" \
      --query "value[].{a:id, b:type, c:location, d:properties.provisioningState}" \
      -o tsv \
      --only-show-errors 2>&1); then
    if [[ "$output" == *"Status code 404"* || "$output" == *"(NotFound)"* || "$output" == *"ResourceNotFound"* ]]; then
      return 0
    fi
    echo "WARNING: Failed to query CapabilityHost resources for $description." >&2
    echo "$output" >&2
    return 0
  fi

  if [[ -z "$output" ]]; then
    return 0
  fi

  while IFS=$'\t' read -r host_id host_type host_location host_state; do
    [[ -z "$host_id" ]] && continue

    strip_cr host_id
    strip_cr host_type
    strip_cr host_location
    strip_cr host_state

    local rg=""
    local account=""
    local project=""
    local capability=""

    IFS='/' read -ra id_parts <<< "$host_id"
    for ((i = 0; i < ${#id_parts[@]}; ++i)); do
      case "${id_parts[i]}" in
        resourceGroups)
          rg="${id_parts[i+1]:-}"
          ;;
        accounts)
          account="${id_parts[i+1]:-}"
          ;;
        projects)
          project="${id_parts[i+1]:-}"
          ;;
        capabilityHosts)
          capability="${id_parts[i+1]:-}"
          ;;
      esac
    done

    if [[ -n "$resource_group" && "$rg" != "$resource_group" ]]; then
      continue
    fi

    found=1
    lines+=("$subscription\t${host_type:-}\t${rg:-}\t${account:-}\t${project:-}\t${capability:-}\t${host_location:-}\t${host_state:-}")
  done <<< "$output"
}

for subscription in "${subscriptions[@]}"; do
  echo "Scanning subscription: $subscription" >&2

  account_args=(
    az cognitiveservices account list
    --subscription "$subscription"
    --query "[].{a:id, b:name, c:resourceGroup}"
    -o tsv
    --only-show-errors
  )
  if [[ -n "$resource_group" ]]; then
    account_args+=(--resource-group "$resource_group")
  fi

  if ! account_output=$("${account_args[@]}" 2>&1); then
    echo "WARNING: Failed to list Cognitive Services accounts in subscription $subscription." >&2
    echo "$account_output" >&2
    continue
  fi

  if [[ -z "$account_output" ]]; then
    continue
  fi

  while IFS=$'\t' read -r account_id account_name account_rg; do
    [[ -z "$account_id" ]] && continue

    strip_cr account_id
    strip_cr account_name
    strip_cr account_rg

    collect_hosts_for_scope "$subscription" "$account_id/capabilityHosts" "account $account_name"

    project_url="https://management.azure.com${account_id}/projects?api-version=${capability_host_api_version}"
    if ! project_output=$(az rest \
        --method get \
        --subscription "$subscription" \
        --url "$project_url" \
        --query "value[].name" \
        -o tsv \
        --only-show-errors 2>&1); then
      if [[ "$project_output" != *"Status code 404"* && "$project_output" != *"(NotFound)"* && "$project_output" != *"ResourceNotFound"* && -n "$project_output" ]]; then
        echo "WARNING: Failed to list projects for Cognitive Services account $account_name." >&2
        echo "$project_output" >&2
      fi
      continue
    fi

    if [[ -z "$project_output" ]]; then
      continue
    fi

    while IFS= read -r project_name; do
      [[ -z "$project_name" ]] && continue
      strip_cr project_name
      collect_hosts_for_scope "$subscription" "$account_id/projects/$project_name/capabilityHosts" "project $project_name in account $account_name"
    done <<< "$project_output"
  done <<< "$account_output"
done

if (( ! found )); then
  echo "No CapabilityHost resources found with the provided filters." >&2
fi

if (( ${#lines[@]} == 0 )); then
  exit 0
fi

if [[ "$output_mode" == "tsv" ]]; then
  printf '%s\n' "${lines[@]}"
else
  if command -v column >/dev/null 2>&1; then
    printf '%s\n' "${lines[@]}" | column -t -s $'\t'
  else
    printf '%s\n' "${lines[@]}"
  fi
fi
