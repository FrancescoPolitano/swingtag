# Runs that need computed values: one mocked apply (the IAM wait sleeps 30 s for real).

# Terraform tests of the module with mocked AWS providers.

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

variables {
  theme_dir   = "./tests/fixtures/themes/good"
  package_dir = "./tests/fixtures/package"
}

run "queue_iam_and_policies" { # no uploader statement by default
  command = apply              # the redrive policy embeds a computed ARN, known only after apply
  assert {
    condition     = aws_sqs_queue.publish.visibility_timeout_seconds == 720 && jsondecode(aws_sqs_queue.publish.redrive_policy).maxReceiveCount == 5
    error_message = "visibility 6 x timeout and 5 receives expected"
  }
  assert {
    condition     = aws_cloudwatch_metric_alarm.dead_letter.threshold == 0 && aws_cloudwatch_metric_alarm.dead_letter.comparison_operator == "GreaterThanThreshold"
    error_message = "alarm on any dead-letter message expected"
  }
}

run "iam_tagging_on_source" {
  command = apply
  assert {
    condition = one([for s in jsondecode(aws_iam_role_policy.publisher.policy).Statement : s.Resource
    if s.Sid == "TagsInSource"]) == "arn:aws:s3:::site-mock/source/*"
    error_message = "the publisher may read and write object tags under source/ only"
  }
}

run "iam_no_wildcards" {
  command = apply
  assert {
    condition = alltrue([for s in jsondecode(aws_iam_role_policy.publisher.policy).Statement :
    alltrue([for r in flatten([s.Resource]) : r != "*"])])
    error_message = "no wildcard resource in the publisher policy"
  }
  assert {
    condition = one([for s in jsondecode(aws_iam_role_policy.publisher.policy).Statement : s.Condition.StringLike["s3:prefix"]
    if s.Sid == "ListSourceAndPublic"]) == ["source/", "source/*", "public/", "public/*"]
    error_message = "ListBucket restricted to source/ and public/"
  }
}

run "uploader_statement_present" { # one principal
  command = apply
  variables { uploader_principal_arns = ["arn:aws:iam::123456789012:user/office"] }
  assert {
    condition = one([for s in jsondecode(aws_s3_bucket_policy.site.policy).Statement : s.Resource
    if s.Sid == "UploadersWriteSourceOnly"]) == "arn:aws:s3:::site-mock/source/*"
    error_message = "uploaders may write source/* only"
  }
}

run "uploader_statement_absent" { # empty list
  command = apply
  assert {
    condition     = !strcontains(aws_s3_bucket_policy.site.policy, "Uploaders")
    error_message = "no uploader statement without principals"
  }
}

