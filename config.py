import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm thư mục gốc của my-mcp-server và nạp file .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ==============================================================================
# Service Hosts & Ports
# ==============================================================================
REST_SERVER_HOST = os.getenv("REST_SERVER_HOST", "127.0.0.1")
REST_SERVER_PORT = int(os.getenv("REST_SERVER_PORT", "8001"))

GRAPHQL_SERVER_HOST = os.getenv("GRAPHQL_SERVER_HOST", "127.0.0.1")
GRAPHQL_SERVER_PORT = int(os.getenv("GRAPHQL_SERVER_PORT", "8002"))

MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8005"))

# ==============================================================================
# Internal Service URLs
# ==============================================================================
REST_API_URL = os.getenv("REST_API_URL", f"http://{REST_SERVER_HOST}:{REST_SERVER_PORT}")
GRAPHQL_URL = os.getenv("GRAPHQL_URL", f"http://{GRAPHQL_SERVER_HOST}:{GRAPHQL_SERVER_PORT}/graphql")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/mcp")

# ==============================================================================
# External Public APIs (Weather & Music)
# ==============================================================================
OPEN_METEO_GEOCODING_URL = os.getenv(
    "OPEN_METEO_GEOCODING_URL",
    "https://geocoding-api.open-meteo.com/v1/search",
)
OPEN_METEO_FORECAST_URL = os.getenv(
    "OPEN_METEO_FORECAST_URL",
    "https://api.open-meteo.com/v1/forecast",
)
ITUNES_SEARCH_URL = os.getenv(
    "ITUNES_SEARCH_URL",
    "https://itunes.apple.com/search",
)

# ==============================================================================
# Keycloak Identity Provider
# ==============================================================================
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8090")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "geoagent")
KEYCLOAK_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
KEYCLOAK_ADMIN_CLIENT_ID = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")

# ==============================================================================
# Distributed Tracing & Observability (OpenTelemetry / Jaeger)
# ==============================================================================
JAEGER_OTLP_ENDPOINT = os.getenv(
    "JAEGER_OTLP_ENDPOINT",
    "http://localhost:4318/v1/traces",
)
