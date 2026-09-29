resource "aws_sqs_queue" "dead_letter" {
  name                      = "${local.prefix}-dead-letter"
  message_retention_seconds = 1209600
  tags                      = var.tags
}

resource "aws_sqs_queue" "publish" {
  name                       = "${local.prefix}-publish"
  visibility_timeout_seconds = 6 * var.lambda_timeout
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dead_letter.arn, maxReceiveCount = 5 })
  tags                       = var.tags
}

resource "aws_sqs_queue_policy" "publish" {
  queue_url = aws_sqs_queue.publish.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "S3Notifications"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.publish.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_s3_bucket.site.arn } }
    }]
  })
}

resource "aws_cloudwatch_metric_alarm" "dead_letter" {
  alarm_name          = "${local.prefix}-unpublished-items"
  alarm_description   = "An item failed to publish five times: see the publisher logs."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dead_letter.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  tags                = var.tags
}
