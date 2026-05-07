terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

resource "digitalocean_container_registry" "main" {
  name                   = var.project_name
  subscription_tier_slug = "basic"
  region                 = "sgp1"
}
