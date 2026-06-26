# Infrastructure (`terraform/`)

Provisions the Azure resources for the MAF agent harness Hosted Agent:
AI Foundry account + project, the **Moonshot AI Kimi K2.6** model deployment
(via Fireworks on Foundry), Azure Container Registry, storage, observability,
and the required role assignments.

## Prerequisites

- **Fireworks preview feature.** Deploying Kimi K2.6 requires the
  `Fireworks.EnableDeploy` preview feature to be **registered on the
  subscription** (one-time, may take up to 30 minutes):

  ```bash
  az feature register --namespace Microsoft.CognitiveServices --name Fireworks.EnableDeploy
  az feature show     --namespace Microsoft.CognitiveServices --name Fireworks.EnableDeploy -o table
  az provider register --namespace Microsoft.CognitiveServices
  ```

  See <https://learn.microsoft.com/azure/foundry/how-to/fireworks/enable-fireworks-models>.

- **Region.** Kimi K2.6 per-token (Data Zone Standard) deployments are available
  in `eastus`, `eastus2`, `centralus`, `northcentralus`, `westus`, `westus3`.
  The default `var.location` is `EastUS2`.

- Azure CLI logged in (`az login`) with rights to create resources, and the
  **Foundry Owner** role on the project to deploy models.

## Usage

```bash
cp env.sample .env && edit .env   # set TF_VAR_subscription_id, TF_VAR_gh_repo
source .env
terraform init
terraform plan
terraform apply
```

## Model configuration

The model is parameterized so you can confirm/override the exact identifiers for
your tenant (`az cognitiveservices account list-models ...`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `model_name` | `FW-Kimi-K2.6` | Catalog Model ID (`properties.model.name`). |
| `model_format` | `Fireworks` | Publisher/collection format. |
| `model_version` | `1` | Model version. |
| `model_sku` | `DataZoneStandard` | Per-token deployment type. |
| `model_deployment_name` | `kimi-k2-6` | Deployment name → `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`. |
| `model_capacity` | `50` | TPM rate limit, in thousands. |

## Wiring outputs to the harness

After `apply`, feed the outputs into the Hosted Agent environment:

```bash
terraform output -raw azure_openai_endpoint   # AZURE_OPENAI_ENDPOINT
terraform output -raw chat_deployment_name    # AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
terraform output -raw container_registry_login_server
```
