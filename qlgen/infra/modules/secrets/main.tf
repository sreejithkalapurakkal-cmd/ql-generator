resource "aws_secretsmanager_secret" "api_keys" {
  name = "${var.project_name}/api-keys"
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    APOLLO_API_KEY = var.apollo_api_key
    EXA_API_KEY    = var.exa_api_key
    HUNTER_API_KEY = var.hunter_api_key
    LUSHA_API_KEY  = var.lusha_api_key
    TAVILY_API_KEY = var.tavily_api_key
    CLAY_API_KEY   = var.clay_api_key
  })
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.project_name}/db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}
