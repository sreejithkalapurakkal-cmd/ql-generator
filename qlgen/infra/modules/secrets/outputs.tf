output "api_keys_secret_arn" {
  value = aws_secretsmanager_secret.api_keys.arn
}

output "db_password_secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}
