mock_provider "aws" {}

run "valid_defaults_plan" {
  command = plan
  assert {
    condition     = length(aws_cloudfront_distribution.d) == 0
    error_message = "no distribution without domain"
  }
}

run "domain_without_zone_rejected" {
  command = plan
  variables { domain_name = "qr.example.com" }
  expect_failures = [var.hosted_zone_name]
}

run "bad_colour_rejected" {
  command = plan
  variables { primary = "red" }
  expect_failures = [aws_s3_bucket.b]
}

run "domain_creates_distribution" {
  command = apply
  variables {
    domain_name      = "qr.example.com"
    hosted_zone_name = "example.com."
  }
  assert {
    condition     = length(aws_cloudfront_distribution.d) == 1
    error_message = "distribution expected"
  }
}
