terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "=4.67.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "=3.1.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "=2.8.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    storage {
      data_plane_available = false
    }
  }

  storage_use_azuread = true

  subscription_id = var.subscription_id
}

provider "azapi" {
  subscription_id = var.subscription_id
}

resource "random_string" "unique" {
  length  = 8
  special = false
  upper   = false
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.gh_repo}-${random_string.unique.result}-${local.loc_for_naming}"
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "other"

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Container registry for the Hosted Agent image
# ---------------------------------------------------------------------------

resource "azurerm_container_registry" "this" {
  name                = "acr${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Standard"
  admin_enabled       = false

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Storage for agent session artifacts
# ---------------------------------------------------------------------------

resource "azurerm_storage_account" "this" {
  name                = "sa${local.func_name}${lower(local.loc_short)}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  shared_access_key_enabled       = false
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  tags = local.tags
}

resource "azurerm_storage_container" "artifacts" {
  name                  = "artifacts"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

# ---------------------------------------------------------------------------
# AI Foundry account + project (Hosted Agents run here)
# ---------------------------------------------------------------------------

resource "azapi_resource" "ai_foundry" {
  type                      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name                      = local.foundry_account_name
  parent_id                 = azurerm_resource_group.this.id
  location                  = azurerm_resource_group.this.location
  schema_validation_enabled = false

  body = {
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }

    properties = {
      disableLocalAuth       = true
      allowProjectManagement = true
      customSubDomainName    = local.foundry_account_name
      publicNetworkAccess    = "Enabled"
      networkAcls = {
        defaultAction = "Allow"
      }
    }
  }

  tags = local.tags
}

resource "azapi_resource" "ai_foundry_project" {
  depends_on = [
    azapi_resource.ai_foundry
  ]

  type                      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name                      = local.foundry_project_name
  parent_id                 = azapi_resource.ai_foundry.id
  location                  = azurerm_resource_group.this.location
  schema_validation_enabled = false

  body = {
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }

    properties = {
      displayName = "project"
      description = "Project hosting the MAF agent harness Hosted Agent"
    }
  }

  response_export_values = [
    "identity.principalId",
    "properties.internalId"
  ]
}

# Model deployment the harness reasons with: Moonshot AI Kimi K2.6 (Fireworks).
resource "azapi_resource" "model" {
  depends_on = [
    azapi_resource.ai_foundry_project
  ]

  type                      = "Microsoft.CognitiveServices/accounts/deployments@2025-06-01"
  name                      = var.model_deployment_name
  parent_id                 = azapi_resource.ai_foundry.id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = var.model_sku
      capacity = var.model_capacity
    }
    properties = {
      model = {
        format  = var.model_format
        name    = var.model_name
        version = var.model_version
      }
    }
  }
}

# The Foundry platform uses the project's system-assigned identity to pull the
# Hosted Agent container image from Azure Container Registry.
resource "azurerm_role_assignment" "foundry_project_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
}

# Connect Application Insights to the project so the Hosted Agent's
# OpenTelemetry traces are exported (the platform injects the connection string).
resource "azapi_resource" "appinsights_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = "appinsights"
  parent_id                 = azapi_resource.ai_foundry_project.id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "AppInsights"
      target        = azurerm_application_insights.this.id
      authType      = "ApiKey"
      isSharedToAll = true
      credentials = {
        key = azurerm_application_insights.this.connection_string
      }
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_application_insights.this.id
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Agent identity + access
#
# A Hosted Agent's *runtime* Entra identity is created by the Foundry platform
# at deploy time (azd grants it "Foundry User" on the account automatically).
# The user-assigned identity below is optional scaffolding: assign it to
# downstream Azure resources the harness should reach (e.g. storage), and pass
# its client id to the agent so DefaultAzureCredential can use it.
# ---------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "agent" {
  name                = "uai-agent-${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  tags = local.tags
}

resource "azurerm_role_assignment" "agent_foundry_access" {
  scope                = azurerm_resource_group.this.id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
}

resource "azurerm_role_assignment" "agent_storage_access" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
}

resource "azurerm_role_assignment" "agent_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
}

# Let the deploying user push images and read agent artifacts
resource "azurerm_role_assignment" "current_user_acr_push" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "current_user_storage" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
