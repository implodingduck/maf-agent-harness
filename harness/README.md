# Agent harness

A [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
**agent harness** built on `create_harness_agent`, talking to an
[Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/) project
via `FoundryChatClient`. It is a lean starter inspired by the official
[harness sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness),
and drives it through that sample's rich
[Textual console UI](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness/console)
(`run_agent_async` + `build_default_observers`).

`create_harness_agent` assembles a batteries-included agent: automatic tool
calling, per-service-call history persistence, context-window compaction, a todo
list for planning, plan/execute mode tracking, web search, and tool-approval
handling. This starter additionally wires a **local shell tool**
(`LocalShellTool` from `agent-framework-tools`) so the agent can run shell
commands and probe its environment. Every command is gated behind an approval
prompt the console surfaces via its `ToolApprovalObserver`.

## The console UI (referenced, not vendored)

The `console` package is an unpublished sample inside the upstream
`microsoft/agent-framework` repo — it is **not** on PyPI. Rather than copying it
in, this repo references it via a **sparse git submodule** at
`external/agent-framework`, pinned to the `python-1.9.0` tag (matching the
`agent-framework` version in `requirements.txt`). Only the harness `console/`
directory is checked out (a blobless partial clone + cone-mode sparse-checkout),
so you don't download the whole framework repo.

Run the one-time setup after cloning this repo:

```bash
scripts/setup-console.sh   # fetches external/agent-framework and sparse-checks-out console/
```

`harness_agent.py` adds that directory to `sys.path` so `from console import ...`
resolves. To update the pin later, check out a new ref inside the submodule and
commit the updated gitlink.

## Layout

| File | Purpose |
| --- | --- |
| `harness_agent.py` | Builds the harness agent (shell tool + Foundry client) and runs the Textual console. |
| `requirements.txt` | Python dependencies (`agent-framework`, `agent-framework-tools`, `textual`, `rich`). |
| `.env.sample` | Local environment variables (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`). |
| `../scripts/setup-console.sh` | One-time setup for the sparse `console` submodule. |
| `../external/agent-framework` | Sparse submodule providing the upstream `console` UI package. |

## Run locally

```bash
git clone --recurse-submodules <this-repo>   # or run scripts/setup-console.sh after cloning
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
../scripts/setup-console.sh   # fetch the console UI submodule (idempotent)
cp .env.sample .env   # fill in FOUNDRY_PROJECT_ENDPOINT + FOUNDRY_MODEL
az login              # AzureCliCredential uses your CLI login
python harness_agent.py
```

Type a task at the console input. When the agent wants to run a shell command
you'll get an interactive approval prompt. Use the console's on-screen help for
available commands (mode switching, todos, session export/import, exit).

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
- The `console` submodule is pinned to the upstream `python-1.9.0` tag to match
  `agent-framework==1.9.0` in `requirements.txt`. If you bump `agent-framework`,
  re-pin the submodule to the matching tag (check out the tag inside
  `external/agent-framework` and commit the updated gitlink) to avoid API drift.
