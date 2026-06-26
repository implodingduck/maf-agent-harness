# Agent harness

A [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
**agent harness** packaged as a [Foundry Hosted Agent](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents).
It exposes an approval-gated local shell tool and uses context compaction, and
serves the **Responses** protocol via `azure.ai.agentserver`.

## Layout

| File | Purpose |
| --- | --- |
| `main.py` | Builds the agent (shell harness + compaction) and starts the hosted server. |
| `requirements.txt` | Python dependencies (`agent-framework`, `agent-framework-tools`, agent server). |
| `Dockerfile` | Container image; serves the Responses protocol on port `8088`. |
| `agent.yaml` | Hosted agent definition (protocol, env vars, model resource) for `azd`. |
| `.env.sample` | Local environment variables. |

## Harness building blocks

- **Local shell with approvals** — `LocalShellTool(mode="stateless",
  approval_mode="always_require")`. Every command surfaces as an approval
  request before it runs; approval is the security boundary. Stateless mode is
  used because a hosted agent serves many isolated sessions.
- **Context compaction** — `InMemoryHistoryProvider` + `SlidingWindowStrategy`
  keep long sessions within the model's token budget.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install --pre -r requirements.txt
cp .env.sample .env   # fill in AZURE_OPENAI_ENDPOINT + deployment name
az login              # DefaultAzureCredential uses your CLI login locally
python main.py        # serves http://localhost:8088 (/health for readiness)
```

## Build & push the image

The Foundry infrastructure (AI Foundry account/project, model deployment,
Azure Container Registry, agent identity) is provisioned in [`../terraform`](../terraform).
Use the `container_registry_login_server` output as the target registry:

```bash
ACR=$(terraform -chdir=../terraform output -raw container_registry_login_server)
az acr login --name "${ACR%%.*}"
docker build -t "$ACR/maf-agent-harness:latest" .
docker push "$ACR/maf-agent-harness:latest"
```

## Deploy as a Hosted Agent

Set `AZURE_OPENAI_ENDPOINT` to the `foundry_project_endpoint`/account endpoint
from the terraform outputs, then deploy with `azd` (using `agent.yaml`) or the
Foundry SDK (`container_protocol_versions=[responses]`). The platform creates
the agent's dedicated Entra identity and endpoint at deploy time.
