locals {
  func_name      = "maf${random_string.unique.result}"
  loc_for_naming = lower(replace(var.location, " ", ""))
  loc_short      = upper("${substr(local.loc_for_naming, 0, 1)}${trimprefix(trimprefix(local.loc_for_naming, "east"), "west")}")
  gh_repo        = split("/", var.gh_repo)[1]

  foundry_account_name = "aif${local.func_name}"
  foundry_project_name = "fp${local.func_name}"
  foundry_endpoint     = "https://${local.foundry_account_name}.services.ai.azure.com/api/projects/${local.foundry_project_name}"

  # Azure OpenAI endpoint for AzureOpenAIChatClient (custom subdomain == account name).
  azure_openai_endpoint = "https://${local.foundry_account_name}.openai.azure.com/"

  tags = {
    "managed_by" = "terraform"
    "repo"       = local.gh_repo
  }
}
