# Agent harness

A [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
**agent harness** built on `create_harness_agent`, talking to an
[Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/) project
via `FoundryChatClient`. It is a lean starter inspired by the official
[harness sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness),
trimmed to the essentials and driven by a simple async REPL (no Textual UI).

`create_harness_agent` assembles a batteries-included agent: automatic tool
calling, per-service-call history persistence, context-window compaction, a todo
list for planning, plan/execute mode tracking, web search, and tool-approval
handling. This starter additionally wires a **local shell tool**
(`LocalShellTool` from `agent-framework-tools`) so the agent can run shell
commands and probe its environment. Every command is gated behind an approval
prompt the REPL surfaces on the terminal.

## Layout

| File | Purpose |
| --- | --- |
| `harness_agent.py` | Builds the harness agent (shell tool + Foundry client) and runs the REPL. |
| `requirements.txt` | Python dependencies (`agent-framework`, `agent-framework-tools`). |
| `.env.sample` | Local environment variables (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`). |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env   # fill in FOUNDRY_PROJECT_ENDPOINT + FOUNDRY_MODEL
az login              # AzureCliCredential uses your CLI login
python harness_agent.py
```

Then type a task at the `you>` prompt. When the agent wants to run a shell
command you'll get an `Approve ...? [y/N]` prompt. Type `/exit` (or `/quit`) to
leave.

The values come from the Foundry infrastructure in
[`../terraform`](../terraform): use the `foundry_project_endpoint` output for
`FOUNDRY_PROJECT_ENDPOINT` and `var.model_deployment_name` (the
`chat_deployment_name` output) for `FOUNDRY_MODEL`. Your identity needs
data-plane access to call the model (for example the **Foundry User** role on the
project); the Terraform currently grants model access to the agent identity, so
add a grant for your own user for local testing.

## Notes

- `create_harness_agent`, `FoundryChatClient`, and `LocalShellTool` require the
  current `agent-framework` (>= 1.9.0). They are **not** compatible with the
  `azure-ai-agentserver-agentframework` Foundry Hosted Agent server wrapper,
  which pins an older `agent-framework-core`. This starter therefore runs as a
  local/console app rather than inside that hosting wrapper.
- Some harness features used by the upstream sample (autonomous execute-mode
  looping via `loop_should_continue`) are not yet in a released `agent-framework`
  version, so they are omitted here.
