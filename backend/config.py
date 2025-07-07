import os
from functools import lru_cache
from google.cloud import secretmanager
from google.api_core import exceptions

@lru_cache(maxsize=None)
def get_secret(secret_id: str) -> str:
    """
    Fetches a secret from Google Secret Manager, with caching.
    Returns the secret payload as a string, or an empty string if not found.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        print("Warning: GCP_PROJECT_ID environment variable not set. Cannot fetch secrets.")
        return ""

    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except exceptions.NotFound:
        print(f"Warning: Secret '{secret_id}' not found in project '{project_id}'.")
        return ""
    except Exception as e:
        # In a real production app, this should go to a structured logger
        print(f"FATAL: An unexpected error occurred while fetching secret '{secret_id}': {e}")
        return ""

class Config:
    """Sets configuration from environment variables and Google Secret Manager."""
    # Non-sensitive config from environment
    POSTGRES_USER = os.environ.get('POSTGRES_USER')
    POSTGRES_DB = os.environ.get('POSTGRES_DB')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND_URL = os.environ.get('CELERY_RESULT_BACKEND_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sensitive config fetched securely from Secret Manager
    SECRET_KEY = get_secret('flask-secret-key')
    POSTGRES_PASSWORD = get_secret('postgres-password')
    GOOGLE_API_KEY = get_secret('google-api-key')
    MUMSNET_USERNAME = get_secret('mumsnet-username')
    MUMSNET_PASSWORD = get_secret('mumsnet-password')
    REDDIT_CLIENT_ID = get_secret('reddit-client-id')
    REDDIT_CLIENT_SECRET = get_secret('reddit-client-secret')
    REDDIT_USERNAME = get_secret('reddit-username')
    REDDIT_PASSWORD = get_secret('reddit-password')

    # Construct the database URI from its component parts
    SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/{POSTGRES_DB}"
    REDIS_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
