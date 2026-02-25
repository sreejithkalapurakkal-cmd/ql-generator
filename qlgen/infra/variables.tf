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
