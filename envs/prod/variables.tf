variable "project" {
  description = "Project name used as a resource name prefix."
  type        = string
  default     = "eks-gitops-platform"
}

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the environment VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "cluster_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.29"
}

variable "node_desired_size" {
  description = "Desired node count for the prod managed node group."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags applied to every resource in this environment."
  type        = map(string)
  default     = {}
}
