import requests
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("RealDataMCP")
GRAPHQL_URL = "http://127.0.0.1:8002/graphql"

def gql(query: str, variables: dict) -> dict:
    res = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        timeout=15,
    ).json()
    if "errors" in res:
        raise RuntimeError(res["errors"][0]["message"])
    return res["data"]

@mcp.tool()
def get_weather(city: str) -> str:
    """Lấy thời tiết thời gian thực (nhiệt độ, độ ẩm, gió) của một thành phố.
    Dùng khi người dùng hỏi về thời tiết, nhiệt độ ở một địa điểm (Hà Nội, Đà Nẵng...).
    """
    try:
        w = gql(
            "query($c:String!){weather(city:$c){city temperature humidity windSpeed}}",
            {"c": city},
        )["weather"]
        return f"{w['city']}: {w['temperature']}°C, độ ẩm {w['humidity']}%, gió {w['windSpeed']} km/h"
    except Exception as e:
        return f"Không thể lấy thời tiết cho '{city}': {str(e)}"

@mcp.tool()
def search_music(query: str, limit: int = 3) -> str:
    """Tìm bài hát trên Apple iTunes theo tên bài hoặc nghệ sĩ (Sơn Tùng M-TP, Binz, Đen Vâu...).
    LƯU Ý: Nếu người dùng yêu cầu số lượng bài hát cụ thể (ví dụ: '4 bài', '5 bài', '10 bài'), bạn PHẢI truyền số đó vào tham số 'limit' (mặc định là 3).
    """
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
        return f"Không thể tìm bài hát: {str(e)}"

if __name__ == "__main__":
    print("MCP Server listening on http://0.0.0.0:8005/sse")
    mcp.run(transport="sse", host="0.0.0.0", port=8005)
