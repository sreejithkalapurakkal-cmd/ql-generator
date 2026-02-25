output "cloudfront_url" {
  value = "https://${module.frontend_cdn.cloudfront_domain_name}"
}

output "alb_url" {
  value = "http://${module.backend_ecs.alb_dns_name}"
}

output "ecr_repository_url" {
  value = module.backend_ecs.ecr_repository_url
}

output "rds_endpoint" {
  value     = module.database.endpoint
  sensitive = true
}

output "frontend_bucket_name" {
  value = module.frontend_cdn.frontend_bucket_name
}

output "cloudfront_distribution_id" {
  value = module.frontend_cdn.cloudfront_distribution_id
}

output "ecs_cluster_name" {
  value = module.backend_ecs.cluster_name
}

output "ecs_service_name" {
  value = module.backend_ecs.service_name
}
