from mcp.server.mcpserver import MCPServer

mcp = MCPServer("MyFirstMCP")

NAME = "Tien"


@mcp.tool()
def lay_ten() -> str:
    """Trả về họ và tên của người dùng.
    BẮT BUỘC gọi công cụ này khi người dùng hỏi bạn có biết tên họ là gì không,
    hỏi tên của họ là gì, hoặc hỏi họ là ai.
    """
    return f"Tên của bạn là {NAME}"

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8005)
