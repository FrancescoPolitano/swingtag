data "archive_file" "publisher" {
  type        = "zip"
  source_dir  = local.package_dir
  output_path = "${path.root}/.terraform/${var.name}-publisher.zip" # per deployment, never outside the root
}

# Key the tokens are derived from. Never rotated: items created later with a
# reused name would get another address.
resource "random_password" "token_secret" {
  length  = 48
  special = false
  lifecycle { ignore_changes = all }
}

resource "aws_iam_role" "publisher" {
  name = "${local.prefix}-publisher"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "publisher" {
  role = aws_iam_role.publisher.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ObjectsInSourceAndPublic"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.site.arn}/source/*", "${aws_s3_bucket.site.arn}/public/*"]
      },
      {
        Sid      = "TagsInSource" # christening copies keep the owner's tags
        Effect   = "Allow"
        Action   = ["s3:GetObjectTagging", "s3:PutObjectTagging", "s3:AbortMultipartUpload"] # managed copy of files over 5 GiB
        Resource = "${aws_s3_bucket.site.arn}/source/*"
      },
      {
        Sid      = "ReadTheme"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.site.arn}/config/theme.json"
      },
      {
        Sid       = "ListSourceAndPublic"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.site.arn
        Condition = { StringLike = { "s3:prefix" = ["source/", "source/*", "public/", "public/*"] } }
      },
      {
        Sid      = "Invalidate"
        Effect   = "Allow"
        Action   = "cloudfront:CreateInvalidation"
        Resource = aws_cloudfront_distribution.site.arn
      },
      {
        Sid      = "PublishQueue"
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:SendMessage"]
        Resource = aws_sqs_queue.publish.arn
      },
      {
        Sid      = "OwnLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.publisher.arn}:*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "publisher" {
  name              = "/aws/lambda/${local.prefix}-publisher"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "publisher" {
  function_name    = "${local.prefix}-publisher"
  role             = aws_iam_role.publisher.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "lambda_function.lambda_handler" # shim written by scripts/build_lambda.sh
  filename         = data.archive_file.publisher.output_path
  source_code_hash = data.archive_file.publisher.output_base64sha256
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory
  environment {
    variables = {
      BUCKET          = aws_s3_bucket.site.id
      SOURCE_PREFIX   = "source/"
      PUBLIC_PREFIX   = "public/"
      CONFIG_KEY      = "config/theme.json"
      PUBLIC_BASE_URL = local.base_url
      DISTRIBUTION_ID = aws_cloudfront_distribution.site.id
      QUEUE_URL       = aws_sqs_queue.publish.id
      TOKEN_SECRET    = random_password.token_secret.result
      LOG_LEVEL       = "INFO"
    }
  }
  tags       = var.tags
  depends_on = [aws_cloudwatch_log_group.publisher, aws_iam_role_policy.publisher]
}

# Never reserved_concurrent_executions with an SQS source: limit the pollers.
resource "aws_lambda_event_source_mapping" "publish" {
  event_source_arn                   = aws_sqs_queue.publish.arn
  function_name                      = aws_lambda_function.publisher.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 30
  function_response_types            = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = 2 }
}

# IAM is eventually consistent: an invocation right after the policy failed.
resource "time_sleep" "iam" {
  create_duration = "30s"
  triggers        = { policy = sha256(aws_iam_role_policy.publisher.policy), role = aws_iam_role.publisher.arn }
}
