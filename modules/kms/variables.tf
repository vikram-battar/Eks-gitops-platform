variable "alias_name" {
  description = "KMS alias name without the 'alias/' prefix."
  type        = string
}

variable "description" {
  description = "Description of the KMS key."
  type        = string
  default     = "Managed by the eks-gitops-platform Terraform stack."
}

variable "deletion_window_in_days" {
  description = "Waiting period before a deleted key is gone for good."
  type        = number
  default     = 30
}

variable "enable_key_rotation" {
  description = "Whether automatic annual key rotation is enabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
