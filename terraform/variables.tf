variable "subscription_id" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "EastUS2"
}

variable "gh_repo" {
  type = string
}

variable "agent_name" {
  type    = string
  default = "maf-harness"
}

# --- Model (Moonshot AI Kimi K2.6 via Fireworks on Foundry) -----------------
# Confirm exact name/format/version for your tenant with:
#   az cognitiveservices account list-models \
#     --name <foundry-account> --resource-group <rg> -o table
# NOTE: deploying Fireworks models requires the subscription preview feature
# "Fireworks.EnableDeploy" to be registered (see terraform/README or the docs:
# https://learn.microsoft.com/azure/foundry/how-to/fireworks/enable-fireworks-models).

# Deployment name surfaced to the harness as AZURE_OPENAI_CHAT_DEPLOYMENT_NAME.
variable "model_deployment_name" {
  type    = string
  default = "kimi-k2-6"
}

# Catalog model id (Model ID column in the Foundry catalog).
variable "model_name" {
  type    = string
  default = "FW-Kimi-K2.6"
}

# Publisher/collection format for the catalog model.
variable "model_format" {
  type    = string
  default = "Fireworks"
}

variable "model_version" {
  type    = string
  default = "1"
}

# Per-token offer for Kimi K2.6 deploys as "Data Zone Standard".
variable "model_sku" {
  type    = string
  default = "DataZoneStandard"
}

# Tokens-per-minute rate limit, in thousands (e.g. 50 = 50K TPM).
variable "model_capacity" {
  type    = number
  default = 50
}
