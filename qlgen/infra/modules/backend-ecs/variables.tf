variable "project_name" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "ecs_security_group_id" {
  type = string
}

variable "db_endpoint" {
  type = string
}

variable "db_username" {
  type    = string
  default = "qlgen"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "api_keys_secret_arn" {
  type = string
}

variable "db_password_secret_arn" {
  type = string
}

variable "cors_allowed_origins" {
  type        = string
  description = "Comma-separated list of allowed CORS origins"
}

variable "google_client_secret" {
  type      = string
  sensitive = true
}

variable "jwt_secret_key" {
  type      = string
  sensitive = true
}

variable "redis_endpoint" {
  type        = string
  description = "ElastiCache Redis endpoint address"
}
