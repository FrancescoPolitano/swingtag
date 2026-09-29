# Fictional example deployment: make demo EXAMPLE=nursery (README "Try it").

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "hosted_zone_name" {
  type    = string
  default = ""
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "swingtag", example = "nursery" }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  default_tags {
    tags = { project = "swingtag", example = "nursery" }
  }
}

module "site" {
  source           = "../../terraform"
  name             = "demo-nursery"
  theme_dir        = "${path.module}/theme"
  force_destroy    = true # examples only: destroy removes every object and version
  domain_name      = var.domain_name
  hosted_zone_name = var.hosted_zone_name
  providers        = { aws = aws, aws.us_east_1 = aws.us_east_1 }
}

locals {
  content_dir = "${path.module}/content"
  # Hidden files (.DS_Store) are left out; everything else goes to source/ as committed.
  files = toset([for f in fileset(local.content_dir, "**") : f if !startswith(basename(f), ".")])
  items = distinct([for f in local.files : join("/", slice(split("/", f), 0, 2))])
  # "{collection} / {label}" => token, from folder names "{collection}/{label} · {token}"
  tokens = { for i in local.items :
    "${split("/", i)[0]} / ${regex("^(.*) · ([a-km-np-z2-9]{12})$", split("/", i)[1])[0]}" =>
    regex("^(.*) · ([a-km-np-z2-9]{12})$", split("/", i)[1])[1]
  }
}

# Uploaded after the module, so the bucket notifications already exist.
resource "aws_s3_object" "content" {
  for_each   = local.files
  bucket     = module.site.bucket
  key        = "source/${each.value}"
  source     = "${local.content_dir}/${each.value}"
  etag       = filemd5("${local.content_dir}/${each.value}")
  depends_on = [module.site]
}

# One republish-all after the uploads: every page is published by the end of the apply.
resource "aws_lambda_invocation" "republish_content" {
  function_name = module.site.function_name
  input         = jsonencode({ action = "republish_all" })
  triggers = {
    content = sha256(join(",", sort([for k, o in aws_s3_object.content : "${k}:${o.etag}"])))
  } # a theme change is republished by the module's own invocation
  depends_on = [aws_s3_object.content]
}

output "pages" {
  value = { for name, token in local.tokens : name => "${module.site.base_url}/${token}" }
}

output "qr_codes" {
  value = { for name, token in local.tokens : name => "${module.site.base_url}/${token}/qr.svg" }
}

output "base_url" { value = module.site.base_url }
output "bucket" { value = module.site.bucket }
output "function_name" { value = module.site.function_name }
output "distribution_id" { value = module.site.distribution_id }
output "dead_letter_queue_url" { value = module.site.dead_letter_queue_url }
output "alarm_name" { value = module.site.alarm_name }
