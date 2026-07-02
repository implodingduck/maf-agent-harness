# Copilot instructions for maf-agent-harness

## What this repository is

This repo builds a **Microsoft Agent Framework (MAF) agent harness** on top of
`create_harness_agent`, talking to an **Azure AI Foundry** project. Supporting
Azure infrastructure is provisioned with **Terraform**.

- Agent harness pattern: <https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework/>
- Harness sample (the starter is based on this): <https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness>

Repository layout:

- `harness/` — the Python MAF harness. `harness_agent.py` builds the agent with
  `create_harness_agent` + `FoundryChatClient` + `LocalShellTool` and runs a lean
  async REPL; `requirements.txt`/`.env.sample` configure it.
- `terraform/` — Azure infrastructure (AI Foundry account + project + model
  deployment, ACR, storage, observability, agent identity, role assignments).

## High-level architecture (target)

The system has two cooperating parts:

1. **Agent harness (application code)** — A MAF agent built with
   `create_harness_agent` (Python `agent-framework`) that connects model
   reasoning to real execution (shell tool + approval flows, todos, plan/execute
   modes, web search, compaction). It talks to the Foundry project via
   `FoundryChatClient` and runs as a local/console app.
2. **Infrastructure (`terraform/`)** — Azure resources the harness needs: an AI
   Foundry account + project, managed identities, observability, storage, and
   networking. Foundry creates the agent's dedicated Entra identity and endpoint
   at deploy time; do not hand-wire those.

Key harness concepts to preserve when editing application code:

- **Use `create_harness_agent`.** Build the agent with
  `create_harness_agent(client=FoundryChatClient(...), shell_executor=LocalShellTool(...), ...)`
  rather than hand-wiring providers. Tune `max_context_window_tokens` /
  `max_output_tokens` to the deployed model.
- **Shell/filesystem tools run behind approval gates.** The shell tool is wired
  via `shell_executor=LocalShellTool(acknowledge_unsafe=True)`; the harness's
  tool-approval flow still gates each command. The REPL surfaces
  `function_approval_request` content as a `[y/N]` prompt and replies with
  `request.to_function_approval_response(approved=...)`. Approval is the real
  security boundary — keep it.
- **Run with the lean REPL.** `harness_agent.py` streams `agent.run(..., stream=True,
  session=session)` and prints `update.text`. There is no Textual UI and no
  hosted-agent server wrapper.
- **Version constraint.** `create_harness_agent` / `FoundryChatClient` /
  `LocalShellTool` need `agent-framework >= 1.9.0`, which is incompatible with the
  `azure-ai-agentserver-agentframework` Hosted Agent wrapper (it pins an older
  `agent-framework-core`). Don't reintroduce that wrapper alongside the harness
  API. Looping (`loop_should_continue`) is not yet in a released version.

## Terraform conventions (`terraform/`)

Follow the style established in
<https://github.com/scallighan/ai-tabletop-co/tree/main/terraform>. Mirror these
patterns exactly when adding resources:

- **File layout:** `main.tf` (provider block + all resources), `locals.tf`,
  `variables.tf`, plus topic files (e.g. `appreg.tf`) as needed. Provide an
  `env.sample` listing the required `TF_VAR_*` exports.
- **Pin provider versions** in the `terraform { required_providers { ... } }`
  block at the top of `main.tf` (this repo's reference uses `azurerm`, `random`,
  `azapi`, `time`, `azuread`). Set `subscription_id = var.subscription_id` on the
  `azurerm` provider.
- **Global-uniqueness suffix:** create one `random_string.unique`
  (`length = 8`, `special = false`, `upper = false`) and build a `func_name`
  local as `"<prefix>${random_string.unique.result}"`. Derive `loc_for_naming`
  (lowercased, de-spaced location) and `loc_short` in `locals.tf`.
- **Naming:** name resources `<type-prefix>-${local.func_name}-${local.loc_for_naming}`
  (resource group `rg-`, vnet `vnet-`, subnet `snet-`, identity `uai-`,
  container app `aca-`, container app env `ace-`; storage/AI accounts drop the
  dash, e.g. `sa…`, `aif…`, `fp…`, `appi…`).
- **Tags:** define a `local.tags` map (`managed_by = "terraform"`,
  `repo = <repo>`) and apply `tags = local.tags` to every taggable resource.
- **AI Foundry via `azapi`:** create the Foundry account and project with
  `azapi_resource` (`Microsoft.CognitiveServices/accounts@2025-06-01` and its
  `/projects` child) rather than a higher-level resource, matching the reference.
- **Identity & access:** give workloads `azurerm_user_assigned_identity`
  resources and grant access with `azurerm_role_assignment` (commonly
  `Foundry User` — formerly `Azure AI User` — and `Storage Blob Data
  Contributor`). Prefer Entra auth
  (`disableLocalAuth`/`local_authentication_enabled = false`, `storage_use_azuread`).
- **Hosted Agent image pull (gotcha):** the Foundry platform pulls the agent
  container with the **project's system-assigned identity**, so grant that
  principal (`azapi_resource.ai_foundry_project.output.identity.principalId`)
  `AcrPull` on the registry. The agent's *runtime* identity is created by the
  platform at deploy time — Terraform can't grant roles to it pre-deploy.
- **Container images:** the harness image lives in the Terraform-created ACR
  (`acr${func_name}`); reference repos use `ghcr.io/${var.gh_repo}/<image>:<tag>`.

### Common variables

`subscription_id` (string, `sensitive`), `location` (default `EastUS2`),
`gh_repo` (string, `owner/repo`), and an `agent_name` where relevant.

## Workflow

- Run Terraform from `terraform/`: `source env.sample`-style exports, then
  `terraform init`, `terraform plan`, `terraform apply`. Format with
  `terraform fmt` and validate with `terraform validate` before committing.
- `*.tfvars`, `*.tfstate*`, and `.terraform/` are git-ignored — never commit
  secrets or state.

## Security

- Keep shell-execution approval gates in place; the upstream guidance is to run
  local shell logic in an isolated environment behind explicit approval.
- Do not put real secrets in Terraform or env files. The reference repo passes a
  Graph client secret inline with a `# TODO put in keyvault` — prefer Key Vault
  / managed identity over inline secrets in new code.
