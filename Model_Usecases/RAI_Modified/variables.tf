variable "resource_group_id" {}

variable "resource_group_name" {
    type        = string
    description = "Name of resource group"
}

variable "environment" {
    type        = string
    description = "The environment where the resources will be deployed"
}

variable "resource_types" {
    description = "map of resource types in azure - imported from root/main.tf"
}

variable "index" {
    type        = string
    description = "The index/version of this app being released e.g. 01, 02, 03... - imported from root/main.tf"
}

variable "jpmc_identifier" {
    description = "identifier for globally uniqueue named services - imported from root/main.tf"
}
variable "resource_group_location" {
    type        = string
    description = "The location where the resources will be deployed"
    #default     = "East US"
}

variable "end_point_subnet_id" {
    # type = string?
    description = "endpoint subnet id obtained from module terraform-azurerm-network"
}

variable "vnet_id" {
    # type = string?
    description = "Vnet id in which private_endpoint subnet located is obtained from module terraform-azurerm-network"
}

variable "openai_base_models" {}
#variable "openai_sa_primary_blob_map" {}
variable "timeout_config" {}

variable "oai_kv_id" {}

variable "oai_kv_uri" {}

variable "oai_kvkey_uri" {}

variable "oai_pvt_dns_zone" {}

variable "law_id" {}

variable "oai_umi_local_name" {
}

variable "oai_local_name" {
}

variable "oai_location" {
}

variable "oai_pe_local_name" {
}

variable "oai_conn_local_name" {
}
variable "oai_dzg_local_name" {
}

variable "oai_custom_domain" {
}

/*variable "oai_pe_to_approve_list" {
    description = "List of Private Endpoints for Open AI to be approved which are external to the subscription"
    type = list(string)
}*/

variable "oai_pe_to_approve" {
    type = list(string)
}

variable "management_apim_jet_obj_id" {
}

variable "management_apim_jet_obj_id_new" {
}

variable "management_apim_smi_obj_id_1" {}

variable "management_apim_smi_obj_id_2" {}

variable "general_index" {}

variable "management_apim_jet_obj_id_west_us_3" {}

variable "management_apim_smi_obj_id_west_us_3" {}

variable "management_apim_jet_identity_obj_id" {}

variable "function_app_umi_object_id" {}

variable "function_app_umi_object_id_wus3" {}

variable "default_rai_policy" {
    type        = string
    description = "The default RAI policy name to be applied to model deployments"
    default     = "Microsoft.Default"
}

variable "cognitive_kind" {}

variable "content_filter_policy" {
    type        = string
    description = "Content filter policy: 'custom' for JPMC custom filter, 'default' for Azure DefaultV2"
    default     = "custom"
}
