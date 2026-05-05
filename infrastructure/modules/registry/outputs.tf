output "endpoint" {
  description = "Container registry endpoint"
  value       = digitalocean_container_registry.main.endpoint
}

output "name" {
  description = "Container registry name"
  value       = digitalocean_container_registry.main.name
}
