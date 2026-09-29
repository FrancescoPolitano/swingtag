# Terraform tests of the module with mocked AWS providers.

mock_provider "aws" {
  mock_resource "aws_cloudfront_distribution" {
    defaults = {
      arn            = "arn:aws:cloudfront::123456789012:distribution/EMOCK"
      domain_name    = "dmock.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
    }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::site-mock" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:eu-west-1:123456789012:mock" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:eu-west-1:123456789012:log-group:mock" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock" }
  }
}

mock_provider "aws" {
  alias = "us_east_1"
  # Real AWS knows the validation domain names at plan time (checked on a real deployment).
  mock_resource "aws_acm_certificate" {
    defaults = {
      arn = "arn:aws:acm:us-east-1:123456789012:certificate/mock"
      domain_validation_options = [{
        domain_name           = "qr.example.com"
        resource_record_name  = "_mock.qr.example.com."
        resource_record_type  = "CNAME"
        resource_record_value = "_mock.acm-validations.aws."
      }]
    }
  }
}

variables {
  theme_dir   = "./tests/fixtures/themes/good"
  package_dir = "./tests/fixtures/package"
}

run "defaults_plan" {
  command = plan
  assert {
    condition     = length(aws_acm_certificate.site) == 0 && length(aws_route53_record.alias) == 0
    error_message = "no certificate or alias records without a domain"
  }
}

run "domain_without_zone" {
  command = plan
  variables { domain_name = "qr.example.com" }
  expect_failures = [var.hosted_zone_name]
}

run "domain_with_zone" {
  command = plan
  variables {
    domain_name      = "qr.example.com"
    hosted_zone_name = "example.com"
  }
  assert {
    condition     = length(aws_acm_certificate.site) == 1 && length(aws_route53_record.alias) == 2
    error_message = "certificate and A/AAAA alias records expected"
  }
  assert {
    condition     = aws_cloudfront_distribution.site.aliases == toset(["qr.example.com"])
    error_message = "distribution alias expected"
  }
}

run "bad_colour" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-colour" }
  expect_failures = [terraform_data.theme]
}

run "bad_locale" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-locale" }
  expect_failures = [terraform_data.theme]
}

run "missing_logo" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/missing-logo" }
  expect_failures = [terraform_data.theme]
}

run "unknown_top_level_key" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/unknown-key" }
  expect_failures = [terraform_data.theme]
}

run "unknown_string_key" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/unknown-string" }
  expect_failures = [terraform_data.theme]
}

run "partial_dark" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/partial-dark" }
  expect_failures = [terraform_data.theme]
}

run "asset_extension" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-asset" }
  expect_failures = [terraform_data.theme]
}

run "show_updated_not_bool" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-show" }
  expect_failures = [terraform_data.theme]
}

run "contrast_warning" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/low-contrast" }
  expect_failures = [check.contrast]
}

run "notifications_filtered" {
  command = plan
  assert {
    condition = one([for q in aws_s3_bucket_notification.source.queue : q.filter_prefix]) == "source/" && toset(one(
    aws_s3_bucket_notification.source.queue).events) == toset(["s3:ObjectCreated:*", "s3:ObjectRemoved:*"])
    error_message = "notifications must be filtered on source/ for created and removed objects"
  }
}

run "no_reserved_concurrency" { # the configuration check is test_terraform_never_reserves_concurrency
  command = plan
  assert {
    condition = aws_lambda_event_source_mapping.publish.scaling_config[0].maximum_concurrency == 2 && contains(
    aws_lambda_event_source_mapping.publish.function_response_types, "ReportBatchItemFailures")
    error_message = "maximum_concurrency 2 and ReportBatchItemFailures expected"
  }
}

run "cloudfront_errors" {
  command = plan
  assert {
    condition = toset([for e in aws_cloudfront_distribution.site.custom_error_response : "${e.error_code}:${e.response_code}:${e.response_page_path}"]) == toset([
    "403:404:/404.html", "404:404:/404.html"])
    error_message = "403 and 404 must map to /404.html with status 404"
  }
}

run "csp_media_src" {
  command = plan
  assert {
    condition     = strcontains(aws_cloudfront_response_headers_policy.security.security_headers_config[0].content_security_policy[0].content_security_policy, "media-src 'self'")
    error_message = "the CSP must allow same-origin media"
  }
}

run "origin_path_public" {
  command = plan
  assert {
    condition     = one(aws_cloudfront_distribution.site.origin).origin_path == "/public"
    error_message = "origin path /public expected"
  }
}

run "theme_json_uploaded" {
  command = plan
  assert {
    condition     = aws_s3_object.theme.key == "config/theme.json" && jsondecode(aws_s3_object.theme.content).locale == "it"
    error_message = "config/theme.json with the theme expected"
  }
  assert {
    condition     = aws_s3_object.asset["logo.svg"].key == "public/_assets/logo.svg" && aws_s3_object.asset["logo.svg"].content_type == "image/svg+xml"
    error_message = "the logo must be published under public/_assets/"
  }
}

run "republish_triggers_first" { # first half: the trigger exists
  command = plan
}

run "republish_triggers_changed" { # an asset change changes the trigger
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/changed-asset" }
  assert {
    condition     = aws_lambda_invocation.republish.triggers.theme != run.republish_triggers_first.theme_fingerprint && aws_lambda_invocation.republish.triggers.theme == output.theme_fingerprint
    error_message = "changing an asset must change the republish trigger"
  }
}

run "wrong_value_types_footer" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-footer-type" }
  expect_failures = [terraform_data.theme]
}

run "wrong_value_types_header" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-header-type" }
  expect_failures = [terraform_data.theme]
}

run "wrong_value_types_string" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-string-value" }
  expect_failures = [terraform_data.theme]
}

run "theme_file_empty" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/empty-file" }
  expect_failures = [terraform_data.theme]
}

run "theme_file_list" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/top-list" }
  expect_failures = [terraform_data.theme]
}

run "theme_extra_colour" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/extra-colour" }
  expect_failures = [terraform_data.theme]
}

run "assets_hidden_ignored" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/dotfile-asset" }
  assert {
    condition     = keys(aws_s3_object.asset) == ["logo.svg"]
    error_message = "hidden files in assets/ must be ignored"
  }
}

run "assets_subfolder_rejected" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/subfolder-asset" }
  expect_failures = [terraform_data.theme]
}

run "assets_bad_name_rejected" {
  command = plan
  variables { theme_dir = "./tests/fixtures/themes/bad-logo-name" }
  expect_failures = [terraform_data.theme]
}

run "bucket_lifecycle_and_ipv6" {
  command = plan
  assert {
    condition     = one(aws_s3_bucket_lifecycle_configuration.site.rule).abort_incomplete_multipart_upload[0].days_after_initiation == 1
    error_message = "incomplete multipart uploads must be aborted after 1 day"
  }
  assert {
    condition     = one(aws_s3_bucket_lifecycle_configuration.site.rule).expiration[0].expired_object_delete_marker == true
    error_message = "expired delete markers must be removed"
  }
  assert {
    condition     = aws_cloudfront_distribution.site.is_ipv6_enabled == true
    error_message = "IPv6 must be enabled (AAAA alias)"
  }
}

run "republish_on_base_address" { # a new base address republishes every page and QR code
  command = plan
  variables {
    domain_name      = "qr.example.com"
    hosted_zone_name = "example.com"
  }
  assert {
    condition     = lookup(aws_lambda_invocation.republish.triggers, "base_url", "") == "https://qr.example.com"
    error_message = "the republish-all triggers must carry the public base address"
  }
}
