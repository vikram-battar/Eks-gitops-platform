# eks-gitops-platform

I built this to have one repo that shows how I'd stand up a real EKS platform: Terraform for the infra, ArgoCD for GitOps delivery, Kyverno for policy guardrails, Prometheus/Grafana for observability. Two environments (dev, prod), same modules, different sizing.

Nothing here came from any employer — I wrote it from scratch as a reference for how I work.

## how it's wired

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

GitHub is the source of truth. ArgoCD syncs two apps — platform policies first (sync waves), then the sample web app. The cluster runs a managed node group with IRSA, Kyverno policies, and kube-prometheus-stack.

The Terraform side (`modules/`, `envs/`) builds the VPC, EKS cluster, KMS key, and an IRSA role for `external-dns`. There's also a small Lambda + Step Functions workflow for idempotent provisioning (tag the VPC, ensure the IAM role and KMS key/alias exist), and a CloudFormation baseline VPC for accounts where the full Terraform stack is overkill.

## repo layout

- `modules/vpc`, `modules/eks`, `modules/iam-irsa`, `modules/kms` — the building blocks
- `envs/dev`, `envs/prod` — environment stacks, same modules, different sizes
- `argocd/apps` — ArgoCD Applications (policies sync before the app)
- `policies/kyverno` — ClusterPolicies: `require-run-as-non-root`, `disallow-latest-tag`
- `helm/app-values.yaml` — values for the sample web app
- `monitoring` — prometheus values + a Grafana dashboard
- `lambda/provisioning`, `step-functions` — provisioning automation
- `cloudformation/baseline.yaml` — cheap baseline network
- `.github/workflows/ci.yml` — `terraform fmt`, `validate`, Checkov on every push

## run it

You need Terraform >= 1.5, AWS CLI v2, kubectl, helm, Python 3.12. Terraform state expects an S3 bucket + DynamoDB table, or just use local state.

```bash
cd envs/dev
cp terraform.tfvars.example terraform.tfvars   # fill in your values
terraform init \
  -backend-config="bucket=<your-tfstate-bucket>" \
  -backend-config="key=eks-gitops-platform/dev/terraform.tfstate" \
  -backend-config="region=us-east-1"
terraform plan -out dev.tfplan
terraform apply dev.tfplan

aws eks update-kubeconfig --region us-east-1 --name eks-gitops-platform-dev-eks

# argocd
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/apps/

# policies (or let argocd deliver them)
kubectl apply -f policies/kyverno/

# monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
```

The `123456789012` account IDs in the Lambda/Step Functions steps are placeholders — use your own. No real credentials anywhere in this repo.

## license

MIT.
