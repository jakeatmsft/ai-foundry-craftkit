#!/usr/bin/env bash
set -euo pipefail

# Assigns a Cosmos DB SQL built-in role to a principal for a specific account.

usage() {
    cat <<'USAGE'
Usage: grant_cosmosdb_data_access.sh --resource-group <name> --account-name <name> [options]

Options:
  -g, --resource-group   Name of the resource group (required)
  -n, --account-name     Cosmos DB account name (required)
  -p, --principal-id     Principal object ID to assign. Defaults to the signed-in user.
  -r, --role-name        Cosmos SQL role display name. Defaults to "Cosmos DB Built-in Data Contributor".
  -h, --help             Show this help and exit.
USAGE
}

resource_group=""
account_name=""
principal_id=""
role_name="Cosmos DB Built-in Data Contributor"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -g|--resource-group)
            resource_group=${2:-}
            shift 2
            ;;
        -n|--account-name)
            account_name=${2:-}
            shift 2
            ;;
        -p|--principal-id)
            principal_id=${2:-}
            shift 2
            ;;
        -r|--role-name)
            role_name=${2:-}
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac

done

if [[ -z "$resource_group" || -z "$account_name" ]]; then
    echo "Both --resource-group and --account-name are required." >&2
    usage >&2
    exit 1
fi

if ! command -v az >/dev/null 2>&1; then
    echo "Azure CLI (az) is required but not installed." >&2
    exit 1
fi

if [[ -z "$principal_id" ]]; then
    principal_id=$(az ad signed-in-user show --query id -o tsv)
    if [[ -z "$principal_id" ]]; then
        echo "Unable to determine the signed-in user's principal ID. Specify --principal-id." >&2
        exit 1
    fi
fi

role_definition_id=""
while IFS=$'\t' read -r role display_id; do
    if [[ "$role" == "$role_name" ]]; then
        role_definition_id="$display_id"
        break
    fi
done < <(az cosmosdb sql role definition list \
    --resource-group "$resource_group" \
    --account-name "$account_name" \
    --query "[].{roleName:roleName,id:id}" -o tsv)

if [[ -z "$role_definition_id" ]]; then
    echo "Role definition '$role_name' not found." >&2
    exit 1
fi

scope=$(az cosmosdb show --resource-group "$resource_group" --name "$account_name" --query id -o tsv)
if [[ -z "$scope" ]]; then
    echo "Unable to resolve Cosmos DB account scope." >&2
    exit 1
fi

existing_assignment=$(az cosmosdb sql role assignment list \
    --resource-group "$resource_group" \
    --account-name "$account_name" \
    --query "[?principalId=='${principal_id}' && roleDefinitionId=='${role_definition_id}' && scope=='${scope}'].id | [0]" -o tsv)

if [[ -n "$existing_assignment" ]]; then
    echo "Role already assigned (assignment ID: $existing_assignment)."
    exit 0
fi

assignment_id=$(az cosmosdb sql role assignment create \
    --resource-group "$resource_group" \
    --account-name "$account_name" \
    --role-definition-id "$role_definition_id" \
    --principal-id "$principal_id" \
    --scope "$scope" \
    --query id -o tsv)

echo "Role assignment created: $assignment_id"
