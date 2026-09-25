# T-24: `terraform test` with a mocked AWS provider can exercise variable
# validations, resource preconditions and check blocks without credentials.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}
variable "domain_name" {
  type    = string
  default = ""
}
variable "hosted_zone_name" {
  type    = string
  default = ""
  validation {
    condition     = var.domain_name == "" || var.hosted_zone_name != ""
    error_message = "hosted_zone_name is required when domain_name is set."
  }
}
variable "primary" {
  type    = string
  default = "#8a2d1c"
}
resource "aws_s3_bucket" "b" {
  bucket = "exp-bucket"
  lifecycle {
    precondition {
      condition     = can(regex("^#[0-9a-fA-F]{6}$", var.primary))
      error_message = "colors.primary must be #rrggbb."
    }
  }
}
resource "aws_cloudfront_distribution" "d" {
  count   = var.domain_name == "" ? 0 : 1
  enabled = true
  origin {
    domain_name = "x.s3.amazonaws.com"
    origin_id   = "s3"
  }
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate { cloudfront_default_certificate = true }
}
