resource "aws_s3_bucket" "site" {
  bucket        = local.prefix
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" } # SSE-KMS would change ETags
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = var.noncurrent_version_expiration_days }
    expiration { expired_object_delete_marker = true }
    abort_incomplete_multipart_upload { days_after_initiation = 1 } # parts are billed until aborted
  }
  depends_on = [aws_s3_bucket_versioning.site]
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "CloudFrontReadsPublicOnly"
          Effect    = "Allow"
          Principal = { Service = "cloudfront.amazonaws.com" }
          Action    = "s3:GetObject"
          Resource  = "${aws_s3_bucket.site.arn}/public/*"
          Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site.arn } }
        },
        {
          Sid       = "DenyInsecureTransport"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource  = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
          Condition = { Bool = { "aws:SecureTransport" = "false" } }
        },
      ],
      [for s in [
        {
          Sid       = "UploadersWriteSourceOnly"
          Effect    = "Allow"
          Principal = { AWS = var.uploader_principal_arns }
          Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
          Resource  = "${aws_s3_bucket.site.arn}/source/*"
        },
        {
          Sid       = "UploadersListSourceOnly"
          Effect    = "Allow"
          Principal = { AWS = var.uploader_principal_arns }
          Action    = "s3:ListBucket"
          Resource  = aws_s3_bucket.site.arn
          Condition = { StringLike = { "s3:prefix" = ["source/", "source/*"] } }
        },
      ] : s if length(var.uploader_principal_arns) > 0],
    )
  })
  depends_on = [aws_s3_bucket_public_access_block.site]
}

resource "aws_s3_bucket_notification" "source" {
  bucket = aws_s3_bucket.site.id
  queue {
    queue_arn     = aws_sqs_queue.publish.arn
    events        = ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"]
    filter_prefix = "source/" # the publisher's own writes under public/ must not loop back
  }
  depends_on = [aws_sqs_queue_policy.publish]
}
