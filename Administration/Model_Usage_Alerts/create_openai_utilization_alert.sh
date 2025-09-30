#!/usr/bin/env bash
set -euo pipefail

# Creates an Azure Monitor metric alert for an Azure OpenAI deployment that
# fires when the Provisioned Managed Utilization metric rises above 90%.
#
# Required environment variables or CLI arguments:
#   RESOURCE_GROUP            Resource group that hosts the Azure OpenAI account.
#   AOAI_ACCOUNT              Name of the Azure OpenAI (Cognitive Services) account.
#   DEPLOYMENT_NAME           Name of the Azure OpenAI deployment to monitor.
#
# Optional variables:
#   ALERT_NAME                Name of the Azure Monitor alert rule (default: aoai-provisioned-utilization-alert).
#   ACTION_GROUP_ID           Resource ID of an existing action group to attach to the alert.
#   ACTION_GROUP_RG           Resource group for the action group (used when creating a new one).
#   ACTION_GROUP_NAME         Name for the action group to create or reuse.
#   ACTION_GROUP_SHORT_NAME   Short name for the action group (default: AOAIUtil, max 12 chars).
#   ACTION_GROUP_EMAIL        Email address to receive alert notifications when creating an action group.
#   EVALUATION_FREQUENCY      ISO8601 duration between evaluations (default: PT1M).
#   WINDOW_SIZE               ISO8601 duration for metric aggregation window (default: PT5M).
#   SEVERITY                  Azure Monitor severity level (1-4, default: 2).
#
# Usage examples:
#   RESOURCE_GROUP="rg-ai" AOAI_ACCOUNT="my-openai" DEPLOYMENT_NAME="gpt-4o" \
#     ACTION_GROUP_RG="rg-ai" ACTION_GROUP_NAME="aoai-alerts" ACTION_GROUP_EMAIL="oncall@contoso.com" \
#     ./create_openai_utilization_alert.sh
#
#   ./create_openai_utilization_alert.sh --resource-group rg-ai --account my-openai \
#     --deployment gpt-4o --action-group-id "/subscriptions/<sub>/.../actionGroups/existing"

usage() {
  cat <<USAGE
Usage: $0 [options]

Options:
  --resource-group <name>        Resource group of the Azure OpenAI account (or set RESOURCE_GROUP).
  --account <name>               Name of the Azure OpenAI account (or set AOAI_ACCOUNT).
  --deployment <name>            Azure OpenAI deployment name to filter alerts (or set DEPLOYMENT_NAME).
  --alert-name <name>            Alert rule name (default: aoai-provisioned-utilization-alert).
  --action-group-id <id>         Resource ID of an existing action group to attach.
  --action-group-rg <name>       Resource group to create or look up an action group.
  --action-group-name <name>     Name of the action group to create or reuse.
  --action-group-short <name>    Short name for the action group (default: AOAIUtil, max 12 chars).
  --action-group-email <email>   Email address used when creating a new action group.
  --severity <1-4>               Azure Monitor severity (default: 2).
  --evaluation-frequency <dur>   ISO8601 duration between evaluations (default: PT1M).
  --window-size <dur>            ISO8601 evaluation window (default: PT5M).
  -h, --help                     Show this help message.
USAGE
}

RESOURCE_GROUP="${RESOURCE_GROUP:-}"
AOAI_ACCOUNT="${AOAI_ACCOUNT:-}"
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-}"
ALERT_NAME="${ALERT_NAME:-aoai-provisioned-utilization-alert}"
ACTION_GROUP_ID="${ACTION_GROUP_ID:-}"
ACTION_GROUP_RG="${ACTION_GROUP_RG:-}"
ACTION_GROUP_NAME="${ACTION_GROUP_NAME:-}"
ACTION_GROUP_SHORT_NAME="${ACTION_GROUP_SHORT_NAME:-AOAIUtil}"
ACTION_GROUP_EMAIL="${ACTION_GROUP_EMAIL:-}"
EVALUATION_FREQUENCY="${EVALUATION_FREQUENCY:-PT1M}"
WINDOW_SIZE="${WINDOW_SIZE:-PT5M}"
SEVERITY="${SEVERITY:-2}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group)
      RESOURCE_GROUP="$2"; shift 2 ;;
    --account)
      AOAI_ACCOUNT="$2"; shift 2 ;;
    --deployment)
      DEPLOYMENT_NAME="$2"; shift 2 ;;
    --alert-name)
      ALERT_NAME="$2"; shift 2 ;;
    --action-group-id)
      ACTION_GROUP_ID="$2"; shift 2 ;;
    --action-group-rg)
      ACTION_GROUP_RG="$2"; shift 2 ;;
    --action-group-name)
      ACTION_GROUP_NAME="$2"; shift 2 ;;
    --action-group-short)
      ACTION_GROUP_SHORT_NAME="$2"; shift 2 ;;
    --action-group-email)
      ACTION_GROUP_EMAIL="$2"; shift 2 ;;
    --severity)
      SEVERITY="$2"; shift 2 ;;
    --evaluation-frequency)
      EVALUATION_FREQUENCY="$2"; shift 2 ;;
    --window-size)
      WINDOW_SIZE="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$RESOURCE_GROUP" || -z "$AOAI_ACCOUNT" || -z "$DEPLOYMENT_NAME" ]]; then
  echo "ERROR: RESOURCE_GROUP, AOAI_ACCOUNT, and DEPLOYMENT_NAME are required." >&2
  usage
  exit 1
fi

if [[ -z "$ACTION_GROUP_ID" ]]; then
  if [[ -z "$ACTION_GROUP_NAME" || -z "$ACTION_GROUP_RG" ]]; then
    echo "ERROR: Provide ACTION_GROUP_ID or both ACTION_GROUP_NAME and ACTION_GROUP_RG to create/reuse an action group." >&2
    exit 1
  fi

  if (( ${#ACTION_GROUP_SHORT_NAME} == 0 || ${#ACTION_GROUP_SHORT_NAME} > 12 )); then
    echo "ERROR: ACTION_GROUP_SHORT_NAME must be between 1 and 12 characters." >&2
    exit 1
  fi

  echo "Looking for existing action group '$ACTION_GROUP_NAME' in resource group '$ACTION_GROUP_RG'..." >&2
  if ! ACTION_GROUP_ID=$(az monitor action-group show \
        --name "$ACTION_GROUP_NAME" \
        --resource-group "$ACTION_GROUP_RG" \
        --query id -o tsv 2>/dev/null); then
    if [[ -z "$ACTION_GROUP_EMAIL" ]]; then
      echo "ERROR: ACTION_GROUP_EMAIL is required to create a new action group." >&2
      exit 1
    fi

    echo "Creating action group '$ACTION_GROUP_NAME' in resource group '$ACTION_GROUP_RG'..." >&2
    ACTION_GROUP_ID=$(az monitor action-group create \
        --name "$ACTION_GROUP_NAME" \
        --resource-group "$ACTION_GROUP_RG" \
        --short-name "$ACTION_GROUP_SHORT_NAME" \
        --query id -o tsv \
        --action email OnCall "$ACTION_GROUP_EMAIL")
  else
    echo "Found existing action group: $ACTION_GROUP_ID" >&2
  fi
fi

if ! [[ "$SEVERITY" =~ ^[1-4]$ ]]; then
  echo "ERROR: SEVERITY must be an integer between 1 and 4." >&2
  exit 1
fi

echo "Resolving Azure OpenAI account scope..." >&2
SCOPE=$(az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AOAI_ACCOUNT" \
  --query id -o tsv)

echo "Creating dimension filter for deployment '$DEPLOYMENT_NAME'..." >&2
DIMENSION=$(az monitor metrics alert dimension create \
  --name ModelDeploymentName \
  --op Include \
  --value "$DEPLOYMENT_NAME" \
  -o tsv)

echo "Building metric alert condition for AzureOpenAIProvisionedManagedUtilizationV2..." >&2
CONDITION=$(az monitor metrics alert condition create \
  --metric AzureOpenAIProvisionedManagedUtilizationV2 \
  --aggregation Maximum \
  --op GreaterThanOrEqual \
  --type static \
  --threshold 90 \
  --dimension "$DIMENSION" \
  -o tsv)

echo "Creating/Updating Azure Monitor alert '$ALERT_NAME'..." >&2
az monitor metrics alert create \
  --name "$ALERT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$SCOPE" \
  --description "Azure OpenAI deployment $DEPLOYMENT_NAME utilization >= 90%" \
  --evaluation-frequency "$EVALUATION_FREQUENCY" \
  --window-size "$WINDOW_SIZE" \
  --severity "$SEVERITY" \
  --condition "$CONDITION" \
  ${ACTION_GROUP_ID:+--action "$ACTION_GROUP_ID"}

echo "Alert rule '$ALERT_NAME' successfully configured." >&2
