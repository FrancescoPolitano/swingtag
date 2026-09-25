# Experiments T-09, T-10, T-19, T-20, T-21 (local, no provider).
# T-09: a check block reports a warning and does not fail the plan.
# T-10: WCAG contrast ratio is computable in HCL (pow exists); the gold
#        primary here fails 3:1 on purpose to show the warning.
# T-19: unknown top-level keys can be rejected.
# T-20: jsonencode(yamldecode(...)) preserves unicode.
# T-21: a variable validation can reference another variable (Terraform >= 1.9).
terraform {
  required_version = ">= 1.9"
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
locals {
  theme   = yamldecode(file("theme/theme.yaml"))
  allowed = ["locale", "timezone", "logo", "header", "footer", "notice", "colors", "colors_dark", "strings"]
  unknown = setsubtract(keys(local.theme), local.allowed)
  # sRGB relative luminance per WCAG 2.x
  lum = { for k, hex in local.theme.colors : k => sum([
    for i, w in [0.2126, 0.7152, 0.0722] : w * (
      parseint(substr(hex, 1 + 2 * i, 2), 16) / 255 <= 0.04045
      ? parseint(substr(hex, 1 + 2 * i, 2), 16) / 255 / 12.92
      : pow((parseint(substr(hex, 1 + 2 * i, 2), 16) / 255 + 0.055) / 1.055, 2.4)
    )
  ]) }
  ratio_text  = (max(local.lum.text, local.lum.background) + 0.05) / (min(local.lum.text, local.lum.background) + 0.05)
  ratio_primary = (max(local.lum.primary, local.lum.background) + 0.05) / (min(local.lum.primary, local.lum.background) + 0.05)
  json        = jsonencode(local.theme)
}
check "contrast" {
  assert {
    condition     = local.ratio_text >= 4.5
    error_message = "theme.yaml: text on background contrast is ${format("%.2f", local.ratio_text)}:1, below 4.5:1."
  }
  assert {
    condition     = local.ratio_primary >= 3
    error_message = "theme.yaml: primary on background contrast is ${format("%.2f", local.ratio_primary)}:1, below 3:1 (icons, WCAG 1.4.11)."
  }
}
resource "terraform_data" "theme" {
  input = local.json
  lifecycle {
    precondition {
      condition     = length(local.unknown) == 0
      error_message = "theme.yaml: unknown keys: ${join(", ", local.unknown)}."
    }
  }
}
output "ratio_text" { value = format("%.2f", local.ratio_text) }
output "ratio_primary" { value = format("%.2f", local.ratio_primary) }
output "json" { value = local.json }
