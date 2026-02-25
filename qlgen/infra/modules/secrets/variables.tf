variable "project_name" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "apollo_api_key" {
  type      = string
  sensitive = true
}

variable "exa_api_key" {
  type      = string
  sensitive = true
}

variable "hunter_api_key" {
  type      = string
  sensitive = true
}

variable "lusha_api_key" {
  type      = string
  sensitive = true
}

variable "tavily_api_key" {
  type      = string
  sensitive = true
}

variable "clay_api_key" {
  type      = string
  sensitive = true
}
