# the pages output of the restaurant example (mocked apply; the IAM wait sleeps 30 s).

mock_provider "aws" {
  mock_resource "aws_cloudfront_distribution" {
    defaults = {
      arn            = "arn:aws:cloudfront::123456789012:distribution/EMOCK"
      id             = "EMOCK"
      domain_name    = "dmock.cloudfront.net"
      hosted_zone_id = "Z2FDTNDATAQYW2"
    }
  }
  mock_resource "aws_cloudfront_function" {
    defaults = { arn = "arn:aws:cloudfront::123456789012:function/mock-rewrite" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::site-mock", id = "site-mock" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:eu-west-1:123456789012:mock", id = "https://sqs.eu-west-1.amazonaws.com/123456789012/mock" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:eu-west-1:123456789012:log-group:mock" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock", id = "mock" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:eu-west-1:123456789012:function:mock", function_name = "mock" }
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

run "example_pages_output" {
  command = apply
  assert {
    condition = keys(output.pages) == ["Osteria Quattro Mestoli / Menu"] && can(regex(
    "/[a-km-np-z2-9]{12}$", output.pages["Osteria Quattro Mestoli / Menu"]))
    error_message = "pages must list the Menu item with a URL ending in its token"
  }
  assert {
    condition     = endswith(output.qr_codes["Osteria Quattro Mestoli / Menu"], "/qr.svg")
    error_message = "qr_codes must point at qr.svg"
  }
}
