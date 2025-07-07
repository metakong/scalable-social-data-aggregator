# --- Terraform and Provider Configuration ---
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# --- Variable Definitions ---
variable "gcp_project_id" {
  description = "The Google Cloud project ID to deploy resources into."
  type        = string
}

variable "gcp_region" {
  description = "The Google Cloud region for resource deployment."
  type        = string
  default     = "us-central1"
}

# --- Service Account Creation ---
resource "google_service_account" "flask_sa" {
  account_id   = "flask-sa"
  display_name = "Flask Application Service Account"
  description  = "Service account for the main Flask web application."
}

resource "google_service_account" "celery_sa" {
  account_id   = "celery-sa"
  display_name = "Celery Worker Service Account"
  description  = "Service account for the Celery background task workers."
}

resource "google_service_account" "github_actions_sa" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions CI/CD Service Account"
  description  = "Service account for GitHub Actions to interact with GCP."
}

# --- Secret Manager Secret Provisioning ---
locals {
  secret_ids = [
    "google-api-key",
    "mumsnet-username",
    "mumsnet-password",
    "reddit-client-id",
    "reddit-client-secret",
    "reddit-username",
    "reddit-password",
    "flask-secret-key",
    "postgres-password"
  ]
}

resource "google_secret_manager_secret" "app_secrets" {
  for_each = toset(local.secret_ids)

  secret_id = each.key
  replication {
    # This block is now corrected
    auto {}
  }
}

# --- IAM Bindings for Least Privilege Access to Secrets ---

# Grant Flask SA access to its required secrets
resource "google_secret_manager_secret_iam_member" "flask_sa_access_google_api_key" {
  project   = google_secret_manager_secret.app_secrets["google-api-key"].project
  secret_id = google_secret_manager_secret.app_secrets["google-api-key"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.flask_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "flask_sa_access_flask_secret_key" {
  project   = google_secret_manager_secret.app_secrets["flask-secret-key"].project
  secret_id = google_secret_manager_secret.app_secrets["flask-secret-key"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.flask_sa.email}"
}

# Grant Celery SA access to its required secrets
locals {
  celery_accessible_secrets = toset(setsubtract(local.secret_ids, ["flask-secret-key"]))
}

resource "google_secret_manager_secret_iam_member" "celery_sa_access" {
  for_each = local.celery_accessible_secrets

  project   = google_secret_manager_secret.app_secrets[each.key].project
  secret_id = google_secret_manager_secret.app_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.celery_sa.email}"
}   