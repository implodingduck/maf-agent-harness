output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "foundry_account_name" {
  value = local.foundry_account_name
}

output "foundry_project_endpoint" {
  description = "AZURE_AI_PROJECT_ENDPOINT for the Hosted Agent / MAF client"
  value       = local.foundry_endpoint
}

output "azure_openai_endpoint" {
  description = "AZURE_OPENAI_ENDPOINT for the harness (AzureOpenAIChatClient)"
  value       = local.azure_openai_endpoint
}

output "chat_deployment_name" {
  description = "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME for the harness"
  value       = var.model_deployment_name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "agent_identity_client_id" {
  description = "AZURE_CLIENT_ID for the agent's user-assigned managed identity"
  value       = azurerm_user_assigned_identity.agent.client_id
}

output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "application_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}
