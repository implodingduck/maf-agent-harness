# Copilot instructions for maf-agent-harness

## What this repository is

This repo builds a **Microsoft Agent Framework (MAF) agent harness** that is
packaged as a container and deployed as a **Microsoft Foundry Hosted Agent**.
Supporting Azure infrastructure is provisioned with **Terraform**.

- Agent harness pattern: <https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework/>
- Foundry Hosted Agents: <https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents>

Repository layout:

- `harness/` — the Python MAF harness (Foundry Hosted Agent, Responses protocol).
  `main.py` builds the agent and calls `from_agent_framework(agent).run()`;
  `Dockerfile`/`requirements.txt`/`agent.yaml` package and deploy it.
- `terraform/` — Azure infrastructure (AI Foundry account + project + model
  deployment, ACR, storage, observability, agent identity, role assignments).

## High-level architecture (target)

The system has two cooperating parts:

1. **Agent harness (application code)** — A MAF agent that connects model
   reasoning to real execution (shell/filesystem tools, approval flows, and
   context compaction). Built with `agent-framework` (Python) or
   `Microsoft.Agents.AI` (.NET). It is containerized and pushed to Azure
   Container Registry, then run by Foundry Agent Service as a Hosted Agent.
2. **Infrastructure (`terraform/`)** — Azure resources the harness needs: an AI
   Foundry account + project, managed identities, observability, storage, and
   networking. Foundry creates the agent's dedicated Entra identity and endpoint
   at deploy time; do not hand-wire those.

Key harness concepts to preserve when editing application code:

- **Shell/filesystem tools run behind approval gates.** The harness uses
  `LocalShellTool` from `agent-framework-tools` in `mode="stateless"` with
  `approval_mode="always_require"` (stateless because a hosted agent serves many
  isolated sessions; a persistent shell must not be shared across sessions).
  Approval is the tool's real security boundary — never set
  `approval_mode="never_require"` without `acknowledge_unsafe=True`.
- **Context compaction** keeps long sessions within the token budget. The
  harness wires `InMemoryHistoryProvider("memory", compaction_strategy=
  SlidingWindowStrategy(...))` into `create_agent(context_providers=[...])`.
  Don't remove compaction when adding long-running conversation features.
- **Hosted Agent server.** `main.py` ends with
  `from_agent_framework(agent).run()` (from `azure.ai.agentserver.agentframework`),
  which serves the Responses protocol and a `/health` endpoint on port `8088`.
- **Default to the Responses protocol.** Use Responses unless a webhook/custom
  payload requires Invocations. The protocol set is declared in the agent
  version definition (`agent.yaml` for azd, or `container_protocol_versions`
  via SDK).
- Hosted Agents run in per-session VM-isolated sandboxes with a persistent
  `$HOME` and `/files`; treat session filesystem state as the persistence layer.

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
