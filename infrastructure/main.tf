terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }

  required_version = ">= 1.0"
}

provider "digitalocean" {
  token = var.do_token
}

module "registry" {
  source       = "./modules/registry"
  project_name = var.project_name
}

module "vpc" {
  source       = "./modules/vpc"
  project_name = var.project_name
  region       = var.do_region
}
