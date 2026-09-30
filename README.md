# EKS GitOps Platform

> **This is a portfolio reference implementation.** It demonstrates an
> infrastructure-as-code pattern for a multi-environment EKS platform with
> GitOps delivery, policy enforcement, and observability. It is not a copy of
> any employer's internal systems — all code here was written from scratch as
> a standalone example.

## Architecture (text overview)

```
                    ┌─────────────────────────────┐
                    │        GitHub repo          │
                    │  (this project — git truth) │
                    └──────────────┬──────────────┘
                                   │ Argo CD polls / webhooks
                    ┌──────────────▼──────────────┐
                    │           Argo CD           │
                    │  apps: platform-policies    │
                    │        web-app (helm)       │
                    └──────────────┬──────────────┘
                    ┌──────────────▼──────────────┐
                    │        Amazon EKS           │
                    │  managed node group         │
                    │  IRSA via OIDC provider     │
                    │  Kyverno ClusterPolicies    │
                    │  (runAsNonRoot, no :latest) │
                    └───────┬─────────────┬───────┘
                            │             │
                 ┌──────────▼──┐   ┌──────▼────────┐
                 │ Prometheus  │   │    Grafana    │
                 │ + Alertmgr  │   │  dashboards   │
                 └─────────────┘   └───────────────┘
```

Supporting automation:

- **Terraform** (`modules/`, `envs/`) provisions the VPC, EKS cluster + node
  group, KMS key, and an IRSA role for `external-dns`. `envs/dev` and
  `envs/prod` wire the modules with environment-specific sizing.
- **Lambda** (`lambda/provisioning/handler.py`) is an idempotent provisioning
  function: given `vpc_id`, `role_name`, `kms_alias`, it tags the VPC, ensures
  the IAM role exists, and ensures the KMS key + alias exist.
- **Step Functions** (`step-functions/provisioning-workflow.json`) orchestrates
  the Lambda with retries and a success/failure branch on `$.Payload.status`.
- **CloudFormation** (`cloudformation/baseline.yaml`) is a cheap baseline
  network (VPC + subnets + IGW) for accounts where the full Terraform stack is
  overkill.

## Repository layout

| Path | What it is |
| ---- | ---------- |
| `modules/vpc` | VPC, subnets, IGW, NAT gateways, route tables |
| `modules/eks` | EKS cluster, managed node group, OIDC provider for IRSA |
| `modules/iam-irsa` | IAM role trustable by a Kubernetes service account |
| `modules/kms` | KMS key + alias with rotation enabled |
| `envs/dev`, `envs/prod` | Environment stacks wiring the modules |
| `lambda/provisioning` | Python 3.12 boto3 provisioning Lambda |
| `step-functions` | ASL workflow invoking the Lambda |
| `cloudformation` | Baseline VPC template |
| `helm/app-values.yaml` | Values for the sample web app |
| `argocd/apps` | Argo CD Applications (policies first, then the app) |
| `policies/kyverno` | ClusterPolicies: `require-run-as-non-root`, `disallow-latest-tag` |
| `monitoring` | kube-prometheus-stack values + a Grafana dashboard |
| `.github/workflows/ci.yml` | CI: fmt, validate, py_compile, YAML/JSON checks, Checkov |

## Prerequisites

- Terraform >= 1.5
- AWS CLI v2 with credentials configured (`aws sts get-caller-identity`)
- Python 3.12, kubectl, helm, argocd CLI (for the GitOps parts)
- An S3 bucket + DynamoDB table for Terraform remote state (or use local state)

## Usage

```bash
# 1. Terraform — dev environment
cd envs/dev
cp terraform.tfvars.example terraform.tfvars   # fill in real values
terraform init \
  -backend-config="bucket=<your-tfstate-bucket>" \
  -backend-config="key=eks-gitops-platform/dev/terraform.tfstate" \
  -backend-config="region=us-east-1"
terraform plan -out dev.tfplan
terraform apply dev.tfplan

# 2. Point kubectl at the new cluster
aws eks update-kubeconfig --region us-east-1 --name eks-gitops-platform-dev-eks

# 3. Install Argo CD, then apply the Applications (policies sync first via sync-wave)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f ../../argocd/apps/

# 4. Install Kyverno (policies are delivered by Argo CD, or apply directly)
kubectl apply -f ../../policies/kyverno/

# 5. Install monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f ../../monitoring/prometheus-values.yaml

# 6. Deploy the provisioning Lambda (example)
cd ../../lambda/provisioning
pip install -r requirements.txt -t package/
cp handler.py package/ && cd package && zip -r ../package.zip . && cd ..
aws lambda create-function \
  --function-name eks-gitops-provisioning \
  --runtime python3.12 --handler handler.handler \
  --role arn:aws:iam::123456789012:role/lambda-provisioning-role \
  --zip-file fileb://package.zip

# 7. Create the Step Functions state machine (replace ${ProvisioningLambdaArn})
aws stepfunctions create-state-machine \
  --name eks-gitops-provisioning \
  --definition file://../../step-functions/provisioning-workflow.json \
  --role-arn arn:aws:iam::123456789012:role/stepfunctions-provisioning-role
```

The ARNs above use the placeholder account `123456789012` — replace with your
own. No real credentials or account IDs are committed anywhere in this repo.

## CI

Every push runs `terraform fmt -check`, `terraform validate` on all modules
and environments, Python/YAML/JSON syntax checks, and Checkov. See
`.github/workflows/ci.yml`.

## License

MIT — see [LICENSE](LICENSE).
