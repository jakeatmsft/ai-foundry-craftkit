resource "azurerm_user_assigned_identity" "openaiumi" {
    location            = var.resource_group_location
    name                = "${var.jpmc_identifier}-${var.environment}-${var.oai_umi_local_name}-${var.resource_types.umi}-${var.index}"
    resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "kv_crypto_service_encryption_user" {
    principal_id         = azurerm_user_assigned_identity.openaiumi.principal_id
    scope                = var.oai_kv_id
    role_definition_name = "Key Vault Crypto Service Encryption User"
    principal_type       = "ServicePrincipal"
    lifecycle { ignore_changes = [role_definition_name] }
}

#Commeted until APIM is provisioned in GOLD DEV
resource "azurerm_role_assignment" "apim_user_acess_administrator" {
    count                = (var.general_index == "a1") || (var.general_index == "b2" && (var.index != "b7" && var.index != "b8" && var.index != "b9" && var.index != "b10" && var.index != "b11" && var.index != "b12" && var.index != "b13" && var.index != "b14" && var.index != "b15" && var.index != "b16" && var.index != "b17" && var.index != "b18" && var.index != "b19" && var.index != "b20" && var.index != "b21")) || (var.general_index == "x2" && var.oai_location != "eastus" && var.index != "p27" && var.index != "p28" && var.index != "p29" && var.index != "p30" && var.index != "p31" && var.index != "p32" && var.index != "p33" && var.index != "p34") || (var.general_index == "x1" && var.index != "p17" && var.index != "p18" && var.index != "p35" && var.index != "p36" && var.index != "p37" && var.index != "p38" && var.index != "p39" && var.index != "p40") || (var.general_index == "v2" && var.oai_location != "eastus") || (var.general_index == "v1") || (var.general_index == "02") && (var.index != "b7" && var.index != "b8") ? 1 : 0
    principal_id         = var.management_apim_jet_obj_id
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "User Access Administrator"
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "apim_reader_role_assignment" {
    count                = var.management_apim_jet_obj_id_new != "" ? 1 : 0
    principal_id         = var.management_apim_jet_obj_id_new
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Reader"
    principal_type       = "ServicePrincipal"
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "apim_reader_role_assignment_west_us_3" {
    count                = var.management_apim_jet_obj_id_west_us_3 != "" ? 1 : 0
    principal_id         = var.management_apim_jet_obj_id_west_us_3
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Reader"
    principal_type       = "ServicePrincipal"
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "apim_reader_role_assignment_to_apim_jet_identity" {
    count                = var.management_apim_jet_identity_obj_id != "" ? 1 : 0
    principal_id         = var.management_apim_jet_identity_obj_id
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Reader"
    principal_type       = "ServicePrincipal"
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "oai_contributor_role_apim_1" {
    count                = var.management_apim_smi_obj_id_1 != "" ? 1 : 0
    principal_id         = var.management_apim_smi_obj_id_1
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI Contributor"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "oai_user_role_apim_2_west_us_3" {
    count                = var.management_apim_smi_obj_id_west_us_3 != "" ? 1 : 0
    principal_id         = var.management_apim_smi_obj_id_west_us_3
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI User"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "oai_user_role_apim_2" {
    principal_id         = var.management_apim_smi_obj_id_2
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI User"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

# Create Cognitive Service
resource "azurerm_cognitive_account" "openai_service" {
    name                = "${var.jpmc_identifier}-${var.oai_location}-${var.oai_local_name}-${var.resource_types.openai}${var.index}"
    resource_group_name = var.resource_group_name
    location            = var.oai_location
    kind                = var.cognitive_kind
    sku_name            = "S0"
    local_auth_enabled  = false
    project_management_enabled = var.cognitive_kind == "OpenAI" ? false : true

    network_acls {
        default_action = "Deny"
    }

    identity {
        type         = "UserAssigned"
        identity_ids = [azurerm_user_assigned_identity.openaiumi.id]
    }

    customer_managed_key {
        identity_client_id = azurerm_user_assigned_identity.openaiumi.client_id
        key_vault_key_id   = var.oai_kvkey_uri
    }

    fqdns = [
        # "${each.value.ds_storage_account_name}.blob.core.windows.net",
        trimsuffix(replace(var.oai_kv_uri, "https://", ""), "/")
    ]

    outbound_network_access_restricted = true
    public_network_access_enabled      = false

    custom_subdomain_name = var.oai_custom_domain

    lifecycle {
        ignore_changes = [
            tags,
            customer_managed_key[0].key_vault_key_id
        ]
    }

    timeouts {
        create = var.timeout_config.create_timeout
        read   = var.timeout_config.read_timeout
        update = var.timeout_config.update_timeout
        delete = var.timeout_config.delete_timeout
    }

    depends_on = [
        azurerm_role_assignment.kv_crypto_service_encryption_user,
    ]
}

#resource "azurerm_private_endpoint" "openai" {
#    depends_on                              = [azurerm_cognitive_account.openai_service]
#    name                                    = "${var.jpmc_identifier}-${var.environment}-${var.oai_pe_local_name}-${var.resource_types.end}-${var.index}"
#    location                                = var.resource_group_location
#    resource_group_name                     = var.resource_group_name
#    subnet_id                               = var.end_point_subnet_id
#    #custom_network_interface_name           = "nic-pe-${azurerm_cognitive_account.openai_service.name}"
#
#    private_service_connection {
#        name                           = "${var.resource_group_location}-${var.environment}-${var.oai_conn_local_name}-${var.resource_types.connection}${var.index}"
#        is_manual_connection           = false
#        private_connection_resource_id = azurerm_cognitive_account.openai_service.id
#        subresource_names              = ["account"]
#    }
#
#    private_dns_zone_group {
#        name                 = "default"
#        private_dns_zone_ids = [var.oai_pvt_dns_zone.id]
#    }
#}

resource "azurerm_monitor_diagnostic_setting" "openai_account_1" {
    log_analytics_workspace_id = var.law_id
    name                       = "default"
    target_resource_id         = azurerm_cognitive_account.openai_service.id

    enabled_log {
        category_group = "allLogs"
    }

    metric {
        category = "AllMetrics"
    }
}

resource "azapi_update_resource" "oai_pe_approve" {
    for_each  = toset(var.oai_pe_to_approve)
    type = "Microsoft.CognitiveServices/accounts/privateEndpointConnections@2023-05-01"
    name = each.key
    #name = var.oai_pe_to_approve
    parent_id = azurerm_cognitive_account.openai_service.id
    body = {
        properties = {
            privateLinkServiceConnectionState = {
                description = "Approved via Terraform"
                status      = "Approved"
            }
        }
    }
}

resource "azurerm_role_assignment" "oai_contributor_role_apim_2_west_us_3" {
    count                = var.management_apim_smi_obj_id_west_us_3 != "" ? 1 : 0
    principal_id         = var.management_apim_smi_obj_id_west_us_3
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI Contributor"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "oai_contributor_role_apim_2" {
    principal_id         = var.management_apim_smi_obj_id_2
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI Contributor"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "func_app_oai_contributor_role" {
    principal_id         = var.function_app_umi_object_id
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI Contributor"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}

resource "azurerm_role_assignment" "func_app_oai_contributor_role_wus3" {
    count                = var.function_app_umi_object_id_wus3 != "" ? 1 : 0
    principal_id         = var.function_app_umi_object_id_wus3
    scope                = azurerm_cognitive_account.openai_service.id
    role_definition_name = "Cognitive Services OpenAI Contributor"
    principal_type       = "ServicePrincipal"
    depends_on           = [azurerm_cognitive_account.openai_service]
    lifecycle { ignore_changes = [role_definition_name] }
}
