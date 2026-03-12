variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "qlgen"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "apollo_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "exa_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "hunter_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "lusha_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "tavily_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "clay_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN of ACM certificate for qlgen.gadgeon.com (must be us-east-1)"
}

variable "custom_domain" {
  type    = string
  default = "qlgen.gadgeon.com"
}

variable "cors_allowed_origins" {
  type    = string
  default = "https://qlgen.gadgeon.com"
}
