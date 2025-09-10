import json
import os
import boto3
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()

# Initialize logger
logger = get_logger('RMRForecast', 'INFO')


# Environment variables
SECRET_NAME = os.getenv("SECRET_NAME")
REGION_NAME = os.getenv("REGION_NAME", "us-east-1")  # fallback default

# AWS SDK client
secrets_client = boto3.client("secretsmanager", region_name=REGION_NAME)


def get_secrets(secret_name):
    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return secret

def get_token(username, password, domain, auth_api_url, trace_id):
    payload = {
        "username": username,
        "password": password,
        "domain": domain
    }
    headers = {"X-Request-ID": trace_id,
               "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    response = requests.post(auth_api_url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise ValueError("No token found in auth response.")
    return token

# Retry for protected API
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.5, min=2, max=60),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True
)
def call_base_api(token, trace_id, base_api_url):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": trace_id,
        "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    response = requests.post(base_api_url, headers=headers, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("application/json") and response.text.strip():
        return response.json()
    else:
        logger.warning(f"Non-JSON or empty response from base API: {response.text}")
        return response.text

def lambda_handler(event, context):
    from trace_utils import setup_trace_id
    trace_id = setup_trace_id(logger)
    
    try:
        logger.info("Lambda execution started")

        if not SECRET_NAME:
            raise EnvironmentError("Missing required environment variable: SECRET_NAME")

        # Get all secrets (including credentials and API URLs)
        secret = get_secrets(SECRET_NAME)
        username = secret["username"]
        password = secret["password"]
        auth_api_url = secret["AUTH_API_URL"]
        base_api_url = secret["PROTECTED_API_URL"]
        domain = secret["DOMAIN"]

        logger.info(f"Retrieved credentials for user: {username}")

        # Get token with retry
        token = get_token(username, password, domain, auth_api_url, trace_id)
        logger.info("Token retrieved successfully")

        # Call Base Api
        protected_data = call_base_api(token, trace_id, base_api_url)
        logger.info("Base Api call succeeded")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Success",
                "data": protected_data,
                "traceId": trace_id
            })
        }

    except Exception as e:
        logger.exception("Lambda execution failed")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Error",
                "error": str(e),
                "traceId": trace_id
            })
        }
    finally:
        # Clean up trace ID
        logger.clear_trace_id()
        
# lambda_handler(None, None)  # For local testing purposes only
