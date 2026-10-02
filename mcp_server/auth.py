import time
import requests
from config import (
    KEYCLOAK_URL,
    KEYCLOAK_REALM as REALM,
    KEYCLOAK_ADMIN_USER,
    KEYCLOAK_ADMIN_PASSWORD,
    KEYCLOAK_ADMIN_CLIENT_ID,
)

_token_cache = {"token": None, "expires_at": 0}
_role_cache = {}


def get_admin_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    res = requests.post(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": KEYCLOAK_ADMIN_CLIENT_ID,
            "username": KEYCLOAK_ADMIN_USER,
            "password": KEYCLOAK_ADMIN_PASSWORD,
            "grant_type": "password",
        },
        timeout=5,
    )
    res.raise_for_status()
    data = res.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 60) - 10
    return _token_cache["token"]


def get_user_roles(username: str) -> list[str]:
    now = time.time()
    if username in _role_cache:
        cached_roles, exp = _role_cache[username]
        if now < exp:
            return cached_roles

    try:
        token = get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/users",
            params={"username": username, "exact": "true"},
            headers=headers,
            timeout=5,
        )
        res.raise_for_status()
        users = res.json()
        if not users:
            return []
        uid = users[0]["id"]
        role_res = requests.get(
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{uid}/role-mappings/realm",
            headers=headers,
            timeout=5,
        )
        role_res.raise_for_status()
        roles = [r["name"] for r in role_res.json()]
        _role_cache[username] = (roles, now + 30)
        return roles
    except Exception as e:
        print(f"[Keycloak Auth Error] Không thể tra cứu role cho user '{username}': {e}")
        return []


def check_permission(caller: str, required_role: str) -> tuple[bool, str]:
    """Kiểm tra quyền của người gọi (caller) đối với required_role qua Keycloak.
    
    Tự động chuẩn hóa các định dạng username phổ biến:
    - 'alice' -> 'alice'
    - 'Alice A' -> 'alice'
    - '@alice:localhost' -> 'alice'
    """
    from opentelemetry import trace
    tracer = trace.get_tracer("mcp-server")

    with tracer.start_as_current_span("keycloak:check_permission") as span:
        span.set_attribute("keycloak.caller", str(caller))
        span.set_attribute("keycloak.required_role", required_role)

        if not caller or not str(caller).strip():
            span.set_attribute("keycloak.allowed", False)
            return False, "Lỗi 401 (Unauthorized): Không xác định được danh tính người gửi (caller trống)."

        username = str(caller).strip().lower()
        if username.startswith("@") and ":" in username:
            username = username[1:].split(":")[0]
        if " " in username:
            username = username.split(" ")[0]

        span.set_attribute("keycloak.username", username)
        roles = get_user_roles(username)
        span.set_attribute("keycloak.user_roles", str(roles))

        if "admin" in roles or required_role in roles:
            span.set_attribute("keycloak.allowed", True)
            return True, "Authorized"

        span.set_attribute("keycloak.allowed", False)
        return (
            False,
            f"Lỗi 403 (Permission Denied): Người dùng '{username}' không có quyền truy cập chức năng này theo phân quyền Keycloak. (Yêu cầu role: '{required_role}', role hiện tại: {roles})",
        )
