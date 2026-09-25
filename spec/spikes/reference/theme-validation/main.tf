# Spike S3: can Terraform alone validate theme.yaml and enumerate content
# folders whose names carry spaces, accents and the " · " separator?
# PROVES: yamldecode + check/precondition style validation with clear errors,
#         fileset over unicode paths, a stable fingerprint of theme + assets.
# SHORTCUT: no provider, no resources; validation expressed as outputs +
#           a terraform_data precondition only.
variable "theme_dir" {
  type    = string
  default = "theme"
}

locals {
  theme       = yamldecode(file("${var.theme_dir}/theme.yaml"))
  known_keys  = ["updated", "empty", "not_found_title", "not_found_body"]
  hex         = "^#[0-9a-fA-F]{6}$"
  colors_ok   = alltrue([for k in ["primary", "background", "text"] : can(regex(local.hex, try(local.theme.colors[k], "")))])
  locale_ok   = contains(["en", "it"], try(local.theme.locale, "en"))
  logo_ok     = try(local.theme.logo, null) == null ? true : fileexists("${var.theme_dir}/assets/${local.theme.logo}")
  unknown_str = setsubtract(keys(try(local.theme.strings, {})), local.known_keys)
  assets      = fileset("${var.theme_dir}/assets", "**")
  content     = fileset("content", "**")
  fingerprint = sha256(join("", concat([filesha256("${var.theme_dir}/theme.yaml")], [for f in sort(tolist(local.assets)) : filesha256("${var.theme_dir}/assets/${f}")])))
}

resource "terraform_data" "theme" {
  input = local.fingerprint
  lifecycle {
    precondition {
      condition     = local.colors_ok
      error_message = "theme.yaml: colors.primary, colors.background and colors.text must be #rrggbb."
    }
    precondition {
      condition     = local.locale_ok
      error_message = "theme.yaml: locale must be en or it."
    }
    precondition {
      condition     = local.logo_ok
      error_message = "theme.yaml: logo not found in theme/assets/."
    }
    precondition {
      condition     = length(local.unknown_str) == 0
      error_message = "theme.yaml: unknown keys under strings: ${join(", ", local.unknown_str)}."
    }
  }
}

output "content" { value = local.content }
output "fingerprint" { value = local.fingerprint }
