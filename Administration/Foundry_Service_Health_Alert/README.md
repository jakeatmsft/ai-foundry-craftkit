# AI Foundry Service Health Alert Terraform Module

This configuration provisions a Service Health alert for Azure AI Foundry workloads. It creates a resource group, action group, and activity log alert that forwards Azure Service Health events to a specified email address.

## Prerequisites
- Terraform CLI v1.1+ installed locally.
- Azure CLI authenticated (`az login`) or service principal credentials exported as environment variables (`ARM_CLIENT_ID`, etc.).
- Permissions to create resource groups, action groups, and activity log alerts in the target subscription(s).

## Inputs
| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `email_address` | Yes | Email or distribution list to receive alert notifications. | n/a |
| `subscriptions_list` | No | List of subscription resource IDs to monitor. If empty, uses the current subscription from the authenticated context. | `[]` |
| `resource_group_name` | No | Resource group to host alert resources. | `service_health_rg` |
| `resource_group_location` | No | Azure region for the resource group. | `East US2` |

## Usage
1. Clone or copy the Terraform files to your workspace.
2. Initialize the providers:
   ```bash
   terraform init
   ```
3. Review the execution plan, substituting your email and optional overrides:
   ```bash
   terraform plan \
     -var "email_address=alerts@example.com" \
     -var "subscriptions_list=[\"/subscriptions/00000000-0000-0000-0000-000000000000\"]"
   ```
4. Apply the configuration once the plan looks correct:
   ```bash
   terraform apply \
     -var "email_address=alerts@example.com"
   ```
5. After deployment, trigger or wait for a Service Health event to confirm that the notification arrives as expected.

## Cleanup
To remove all resources created by this project when they are no longer needed:
```bash
terraform destroy \
  -var "email_address=alerts@example.com"
```

## Additional Notes
- If you already have an action group, adjust the configuration to reference it instead of creating a new one.
- Keep `subscriptions_list` aligned with the subscriptions your AI Foundry workloads rely on so alerts are scoped appropriately.
