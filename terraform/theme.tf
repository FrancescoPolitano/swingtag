# Theme: strict validation at plan time, upload, and republish-all on change.

locals {
  theme_file = "${var.theme_dir}/theme.yaml"
  theme_raw  = try(yamldecode(file(local.theme_file)), null)     # an empty file does not decode
  theme_map  = can(keys(local.theme_raw))                        # false for null, lists, scalars
  theme      = try({ for k, v in local.theme_raw : k => v }, {}) # {} for null or scalar input
  theme_keys = ["locale", "timezone", "logo", "header", "footer", "notice", "show_updated", "colors", "colors_dark", "strings"]
  text_keys  = ["locale", "timezone", "logo", "header", "footer", "notice"]
  string_keys = ["updated", "empty", "not_found_title", "not_found_body", "kind_document", "kind_image",
  "kind_audio", "kind_video", "kind_link"]
  colour_keys = ["primary", "background", "text"]
  hex         = "^#[0-9a-fA-F]{6}$"

  strings = try(local.theme.strings == null ? {} : local.theme.strings, {})
  # A value is a string when its JSON form is a quoted string; null means "not set".
  bad_types = concat(
    [for k in local.text_keys : k if contains(keys(local.theme), k) && try(local.theme[k] != null && !startswith(jsonencode(local.theme[k]), "\""), true)],
    [for k, v in local.strings : "strings.${k}" if !startswith(jsonencode(v), "\"")],
  )

  colors         = try(local.theme.colors == null ? {} : local.theme.colors, {})
  colors_ok      = alltrue([for k in local.colour_keys : can(regex(local.hex, local.colors[k]))])
  has_dark       = contains(keys(local.theme), "colors_dark")
  dark           = try(local.theme.colors_dark == null ? {} : local.theme.colors_dark, {})
  dark_ok        = !local.has_dark || (length(keys(local.dark)) == 3 && alltrue([for k in local.colour_keys : can(regex(local.hex, local.dark[k]))]))
  unknown_colour = concat([for k in keys(local.colors) : "colors.${k}" if !contains(local.colour_keys, k)], [for k in keys(local.dark) : "colors_dark.${k}" if !contains(local.colour_keys, k)])
  locale_ok      = contains(["en", "it"], try(local.theme.locale, "en"))
  show_ok        = !contains(keys(local.theme), "show_updated") || try(local.theme.show_updated == true || local.theme.show_updated == false, false)
  unknown_top    = setsubtract(keys(local.theme), local.theme_keys)
  unknown_str    = setsubtract(keys(local.strings), local.string_keys)

  asset_types = { svg = "image/svg+xml", png = "image/png", jpg = "image/jpeg", jpeg = "image/jpeg", webp = "image/webp" }
  asset_files = [for f in fileset("${var.theme_dir}/assets", "**") : f if !startswith(basename(f), ".")] # .DS_Store and co.
  assets      = toset([for f in local.asset_files : f if !strcontains(f, "/")])
  nested      = [for f in local.asset_files : f if strcontains(f, "/")]
  bad_names   = [for f in local.assets : f if !can(regex("^[A-Za-z0-9._-]+$", f))]
  asset_ext   = { for f in local.assets : f => lower(reverse(split(".", f))[0]) }
  bad_assets  = [for f, ext in local.asset_ext : f if !contains(keys(local.asset_types), ext)]
  logo        = try(tostring(local.theme.logo), null)
  logo_ok     = local.logo == null ? true : contains(local.assets, local.logo) # Terraform 1.9 does not short-circuit ||

  fingerprint = sha256(join(",", concat([filesha256(local.theme_file)],
  [for f in sort(tolist(local.assets)) : "${f}:${filesha256("${var.theme_dir}/assets/${f}")}"])))

  # WCAG 2.x relative luminance; computed only for valid colours.
  lum = { for name, set in { light = local.colors, dark = local.dark } : name => (
    !(name == "light" ? local.colors_ok : (local.has_dark && local.dark_ok)) ? {} : { for k in local.colour_keys : k => sum([
      for i, w in [0.2126, 0.7152, 0.0722] : w * (
        parseint(substr(set[k], 1 + 2 * i, 2), 16) / 255 <= 0.04045
        ? parseint(substr(set[k], 1 + 2 * i, 2), 16) / 255 / 12.92
        : pow((parseint(substr(set[k], 1 + 2 * i, 2), 16) / 255 + 0.055) / 1.055, 2.4)
      )
    ]) }
  ) }
  contrast = { for name, l in local.lum : name => length(l) == 0 ? {} : {
    text    = (max(l.text, l.background) + 0.05) / (min(l.text, l.background) + 0.05)
    primary = (max(l.primary, l.background) + 0.05) / (min(l.primary, l.background) + 0.05)
  } }
}

resource "terraform_data" "theme" {
  input = local.fingerprint
  lifecycle {
    precondition {
      condition     = local.theme_map
      error_message = "theme.yaml: must be a YAML mapping of keys (it is empty or not a mapping)."
    }
    precondition {
      condition     = length(local.bad_types) == 0
      error_message = "theme.yaml: these values must be text: ${join(", ", local.bad_types)}."
    }
    precondition {
      condition     = length(local.unknown_colour) == 0
      error_message = "theme.yaml: unknown colour keys: ${join(", ", local.unknown_colour)} (primary, background, text only)."
    }
    precondition {
      condition     = length(local.nested) == 0
      error_message = "theme/assets: subfolders are not supported: ${join(", ", local.nested)}."
    }
    precondition {
      condition     = length(local.bad_names) == 0
      error_message = "theme/assets: use letters, digits, dot, underscore and hyphen in file names: ${join(", ", local.bad_names)}."
    }
    precondition {
      condition     = length(local.unknown_top) == 0
      error_message = "theme.yaml: unknown keys: ${join(", ", local.unknown_top)}."
    }
    precondition {
      condition     = local.colors_ok
      error_message = "theme.yaml: colors.primary, colors.background and colors.text must be #rrggbb."
    }
    precondition {
      condition     = local.dark_ok
      error_message = "theme.yaml: colors_dark needs primary, background and text, each #rrggbb."
    }
    precondition {
      condition     = local.locale_ok
      error_message = "theme.yaml: locale must be en or it."
    }
    precondition {
      condition     = local.show_ok
      error_message = "theme.yaml: show_updated must be true or false."
    }
    precondition {
      condition     = length(local.unknown_str) == 0
      error_message = "theme.yaml: unknown keys under strings: ${join(", ", local.unknown_str)}."
    }
    precondition {
      condition     = local.logo_ok
      error_message = "theme.yaml: logo ${coalesce(local.logo, "?")} not found in theme/assets/."
    }
    precondition {
      condition     = length(local.bad_assets) == 0
      error_message = "theme/assets: unsupported files (svg, png, jpg, jpeg, webp only): ${join(", ", local.bad_assets)}."
    }
  }
}

check "contrast" {
  assert {
    condition     = try(local.contrast.light.text >= 4.5, true)
    error_message = "theme.yaml: text on background contrast is below 4.5:1 (WCAG AA)."
  }
  assert {
    condition     = try(local.contrast.light.primary >= 3, true)
    error_message = "theme.yaml: primary on background contrast is below 3:1 (icons, WCAG 1.4.11)."
  }
  assert {
    condition     = try(local.contrast.dark.text >= 4.5, true) && try(local.contrast.dark.primary >= 3, true)
    error_message = "theme.yaml: colors_dark contrast is below 4.5:1 (text) or 3:1 (primary)."
  }
}

resource "aws_s3_object" "theme" {
  bucket       = aws_s3_bucket.site.id
  key          = "config/theme.json"
  content      = jsonencode(local.theme)
  content_type = "application/json"
  depends_on   = [terraform_data.theme]
}

resource "aws_s3_object" "asset" {
  for_each      = local.asset_ext
  bucket        = aws_s3_bucket.site.id
  key           = "public/_assets/${each.key}"
  source        = "${var.theme_dir}/assets/${each.key}"
  etag          = filemd5("${var.theme_dir}/assets/${each.key}")
  content_type  = local.asset_types[each.value]
  cache_control = "public, max-age=300"
  depends_on    = [terraform_data.theme]
}

resource "aws_lambda_invocation" "republish" {
  function_name = aws_lambda_function.publisher.function_name
  input         = jsonencode({ action = "republish_all" })
  triggers = {
    theme    = local.fingerprint
    package  = data.archive_file.publisher.output_base64sha256
    base_url = local.base_url
  }
  depends_on = [time_sleep.iam, aws_s3_object.theme, aws_s3_object.asset,
  aws_lambda_event_source_mapping.publish, aws_s3_bucket_notification.source]
}
