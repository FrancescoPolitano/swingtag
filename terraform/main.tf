# Terraform module. Every resource name derives from var.name.

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  prefix      = "${var.name}-${random_id.suffix.hex}"
  package_dir = coalesce(var.package_dir, "${path.module}/../build/lambda")
  custom      = var.domain_name != ""
  base_url    = local.custom ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.site.domain_name}"
}
