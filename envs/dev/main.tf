provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}

locals {
  name_prefix = "${var.project}-dev"
  azs         = ["${var.region}a", "${var.region}b", "${var.region}c"]
}

module "vpc" {
  source = "../../modules/vpc"

  name               = local.name_prefix
  cidr_block         = var.vpc_cidr
  azs                = local.azs
  public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24", "10.10.3.0/24"]
  private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24", "10.10.13.0/24"]
  tags               = var.tags
}

module "eks" {
  source = "../../modules/eks"

  cluster_name       = "${local.name_prefix}-eks"
  cluster_version    = var.cluster_version
  private_subnet_ids = module.vpc.private_subnet_ids
  tags               = var.tags
}

module "kms" {
  source = "../../modules/kms"

  alias_name  = "${var.project}/dev"
  description = "Dev environment data encryption key for ${var.project}."
  tags        = var.tags
}

module "irsa_external_dns" {
  source = "../../modules/iam-irsa"

  name                 = "${local.name_prefix}-external-dns"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_issuer_url      = module.eks.cluster_oidc_issuer_url
  namespace            = "kube-system"
  service_account_name = "external-dns"
  policy_arns          = ["arn:aws:iam::aws:policy/AmazonRoute53FullAccess"]
  tags                 = var.tags
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "kms_key_arn" {
  value = module.kms.key_arn
}
