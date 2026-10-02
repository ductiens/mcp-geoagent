import sys
import requests
from mcp.server.mcpserver import MCPServer
from mcp.server.connection import Connection
from mcp_server.auth import check_permission

# Fix triệt để lỗi MCP -32602: Cho phép client SSE (OpenClaw) tự động gọi tool khi reconnect
Connection.initialize_accepted = property(lambda self: True)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tracing import setup_tracer
from config import GRAPHQL_URL, MCP_SERVER_HOST, MCP_SERVER_PORT, MCP_SERVER_URL

tracer = setup_tracer("mcp-server")
mcp = MCPServer("RealDataMCP")


def gql(query: str, variables: dict) -> dict:
    res = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        timeout=25,
    ).json()
    if "errors" in res:
        raise RuntimeError(res["errors"][0]["message"])
    return res["data"]


@mcp.tool()
def get_weather(city: str, caller: str) -> str:
    """Lấy thời tiết thời gian thực (nhiệt độ, độ ẩm, gió) của một thành phố.
    Dùng khi người dùng hỏi về thời tiết, nhiệt độ ở một địa điểm (Hà Nội, Đà Nẵng...).

    :param city: Tên thành phố (ví dụ: 'Hà Nội', 'Đà Nẵng')
    :param caller: Tên tài khoản người gửi tin nhắn (lấy từ trường 'username' trong phần Sender metadata, ví dụ: 'alice', 'bob', 'admin') để xác thực quyền với Keycloak.
    """
    with tracer.start_as_current_span("mcp.tool:get_weather") as span:
        span.set_attribute("tool.name", "get_weather")
        span.set_attribute("tool.city", city)
        span.set_attribute("tool.caller", caller)
        print(f"\n[MCP TOOL CALL] get_weather -> city='{city}', caller='{caller}'")

        # 1. Kiểm tra phân quyền qua Keycloak
        allowed, message = check_permission(caller, "weather_user")
        span.set_attribute("tool.authorized", allowed)
        print(f"[MCP AUTH RESULT] allowed={allowed}, message='{message}'")
        if not allowed:
            span.set_attribute("error", True)
            return message

        # 2. Thực thi nghiệp vụ nếu đã được cấp quyền
        try:
            w = gql(
                "query($c:String!){weather(city:$c){city temperature humidity windSpeed}}",
                {"c": city},
            )["weather"]
            return f"{w['city']}: {w['temperature']}°C, độ ẩm {w['humidity']}%, gió {w['windSpeed']} km/h"
        except Exception as e:
            span.record_exception(e)
            return f"Không thể lấy thời tiết cho '{city}': {str(e)}"


@mcp.tool()
def search_music(query: str, caller: str, limit: int = 3) -> str:
    """Tìm bài hát trên Apple iTunes theo tên bài hoặc nghệ sĩ (Sơn Tùng M-TP, Binz, Đen Vâu...).

    :param query: Tên bài hát hoặc ca sĩ cần tìm.
    :param caller: Tên tài khoản người gửi tin nhắn (lấy từ trường 'username' trong phần Sender metadata, ví dụ: 'alice', 'bob', 'admin') để xác thực quyền với Keycloak.
    :param limit: Số lượng bài hát cần lấy (mặc định là 3).
    """
    with tracer.start_as_current_span("mcp.tool:search_music") as span:
        span.set_attribute("tool.name", "search_music")
        span.set_attribute("tool.query", query)
        span.set_attribute("tool.limit", limit)
        span.set_attribute("tool.caller", caller)
        print(f"\n[MCP TOOL CALL] search_music -> query='{query}', limit={limit}, caller='{caller}'")

        # 1. Kiểm tra phân quyền qua Keycloak
        allowed, message = check_permission(caller, "music_user")
        span.set_attribute("tool.authorized", allowed)
        print(f"[MCP AUTH RESULT] allowed={allowed}, message='{message}'")
        if not allowed:
            span.set_attribute("error", True)
            return message

        # 2. Thực thi nghiệp vụ nếu đã được cấp quyền
        try:
            tracks = gql(
                "query($q:String!, $l:Int!){searchMusic(query:$q, limit:$l){trackName artistName previewUrl}}",
                {"q": query, "l": limit},
            )["searchMusic"]
            return (
                "\n".join(
                    f"{i}. {t['trackName']} - {t['artistName']} {t['previewUrl'] or ''}"
                    for i, t in enumerate(tracks, 1)
                )
                or "Không tìm thấy bài nào."
            )
        except Exception as e:
            span.record_exception(e)
            return f"Không thể tìm bài hát: {str(e)}"


if __name__ == "__main__":
    print(f"MCP Server listening on {MCP_SERVER_URL} (Streamable HTTP)")
    mcp.run(transport="streamable-http", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)
