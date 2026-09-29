variable "name" {
  description = "Prefix of every resource name."
  type        = string
  default     = "swingtag"
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,30}$", var.name))
    error_message = "name must be 2-31 lowercase letters, digits or hyphens."
  }
}

variable "theme_dir" {
  description = "Folder with theme.yaml and an optional assets/ folder."
  type        = string
}

variable "package_dir" {
  description = "Folder with the Lambda package built by scripts/build_lambda.sh; defaults to build/lambda at the repository root."
  type        = string
  default     = null
}

variable "domain_name" {
  description = "Custom domain for the site; empty uses the CloudFront default certificate."
  type        = string
  default     = ""
}

variable "hosted_zone_name" {
  description = "Public Route 53 zone of domain_name."
  type        = string
  default     = ""
  validation {
    condition     = var.domain_name == "" || var.hosted_zone_name != ""
    error_message = "hosted_zone_name is required when domain_name is set."
  }
}

variable "force_destroy" {
  description = "Let terraform destroy delete a bucket that still holds objects and versions."
  type        = bool
  default     = false
}

variable "price_class" {
  type    = string
  default = "PriceClass_100"
}

variable "lambda_timeout" {
  type    = number
  default = 120
}

variable "lambda_memory" {
  type    = number
  default = 512
}

variable "noncurrent_version_expiration_days" {
  type    = number
  default = 90
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "uploader_principal_arns" {
  description = "IAM principals allowed to read, write and delete under source/ only."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "alarm_actions" {
  description = "ARNs notified when an item fails to publish (for example an SNS topic)."
  type        = list(string)
  default     = []
}
