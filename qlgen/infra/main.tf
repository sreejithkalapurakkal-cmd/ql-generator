module "networking" {
  source       = "./modules/networking"
  project_name = var.project_name
}

module "secrets" {
  source         = "./modules/secrets"
  project_name   = var.project_name
  db_password    = var.db_password
  apollo_api_key = var.apollo_api_key
  exa_api_key    = var.exa_api_key
  hunter_api_key = var.hunter_api_key
  lusha_api_key  = var.lusha_api_key
  tavily_api_key = var.tavily_api_key
  clay_api_key   = var.clay_api_key
}

module "database" {
  source                = "./modules/database"
  project_name          = var.project_name
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id
  db_password           = var.db_password
}

module "backend_ecs" {
  source                 = "./modules/backend-ecs"
  project_name           = var.project_name
  aws_region             = var.aws_region
  vpc_id                 = module.networking.vpc_id
  public_subnet_ids      = module.networking.public_subnet_ids
  alb_security_group_id  = module.networking.alb_security_group_id
  ecs_security_group_id  = module.networking.ecs_security_group_id
  db_endpoint            = module.database.endpoint
  db_username            = "qlgen"
  db_password            = var.db_password
  api_keys_secret_arn    = module.secrets.api_keys_secret_arn
  db_password_secret_arn = module.secrets.db_password_secret_arn
  cors_allowed_origins   = var.cors_allowed_origins
  google_client_secret   = var.google_client_secret
  jwt_secret_key         = var.jwt_secret_key
}

module "frontend_cdn" {
  source              = "./modules/frontend-cdn"
  project_name        = var.project_name
  environment         = var.environment
  alb_dns_name        = module.backend_ecs.alb_dns_name
  acm_certificate_arn = var.acm_certificate_arn
  custom_domain       = var.custom_domain
}
