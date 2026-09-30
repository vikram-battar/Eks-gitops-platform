terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state. Fill in bucket/key/region via -backend-config or a
  # backend.hcl file; values below are placeholders on purpose.
  backend "s3" {}
}
