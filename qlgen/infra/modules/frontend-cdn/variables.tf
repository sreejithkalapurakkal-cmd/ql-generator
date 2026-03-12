variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "alb_dns_name" {
  type = string
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN of ACM certificate for the custom domain (must be in us-east-1)"
}

variable "custom_domain" {
  type        = string
  description = "Custom domain alias for the CloudFront distribution"
}
