data "aws_route53_zone" "site" {
  count        = local.custom ? 1 : 0
  name         = var.hosted_zone_name
  private_zone = false
}

resource "aws_acm_certificate" "site" {
  provider          = aws.us_east_1 # CloudFront certificates live in us-east-1
  count             = local.custom ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"
  tags              = var.tags
  lifecycle { create_before_destroy = true }
}

# One domain per certificate, so one validation record: keyed by the (known) domain name.
resource "aws_route53_record" "validation" {
  for_each        = local.custom ? toset([var.domain_name]) : toset([])
  zone_id         = data.aws_route53_zone.site[0].zone_id
  name            = one(aws_acm_certificate.site[0].domain_validation_options).resource_record_name
  type            = one(aws_acm_certificate.site[0].domain_validation_options).resource_record_type
  records         = [one(aws_acm_certificate.site[0].domain_validation_options).resource_record_value]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  provider                = aws.us_east_1
  count                   = local.custom ? 1 : 0
  certificate_arn         = aws_acm_certificate.site[0].arn
  validation_record_fqdns = [for r in aws_route53_record.validation : r.fqdn]
}

resource "aws_route53_record" "alias" {
  for_each = local.custom ? toset(["A", "AAAA"]) : toset([])
  zone_id  = data.aws_route53_zone.site[0].zone_id
  name     = var.domain_name
  type     = each.key
  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}
