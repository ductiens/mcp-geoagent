# Architecture report — Real-Data MCP Gateway (Weather & Music demo)

> Phạm vi: các service đang có trong repository `my-mcp-server`. C1/C2/C3 theo C4 model; hai sequence mô tả hai luồng người dùng chính.  
> Nguồn đối chiếu: `mcp_server/server.py`, `graphql_server/`, `rest_server/main.py`, `docs/`.

## 1. Mục tiêu và phạm vi

Hệ thống Gateway cung cấp dữ liệu thực tế thời gian thực (thời tiết, âm nhạc) từ Internet cho Trợ lý ảo AI (OpenClaw) theo chuẩn **Model Context Protocol (MCP)**. OpenClaw đóng vai trò là client/agent gọi MCP; MCP không tự sinh câu trả lời mà chuyển các tool call xuống GraphQL, rồi GraphQL tổng hợp và lấy dữ liệu từ REST API nội bộ. REST API chịu trách nhiệm trực tiếp gọi các Public API bên ngoài (Open-Meteo, Apple iTunes) và chuẩn hóa dữ liệu.

Các port khi chạy local:
- **REST Service:** `8001` (`/api/weather`, `/api/music`, Swagger UI `/docs`)
- **GraphQL Service:** `8002` (`/graphql`)
- **MCP Service:** `8005` (Transport SSE tại `/sse`)
- **OpenClaw Gateway:** `18789` (Matrix Bot chạy trong Docker, kết nối Matrix Synapse `8008` và Element Web `8080`)

---

## 2. C1 — System Context

```mermaid
flowchart LR
    user["Người dùng / Client\nHỏi thời tiết, bài hát"]
    agent["OpenClaw Gateway\nAI Matrix Bot / Agent Client"]
    system["Real-Data Gateway Services\nMCP + GraphQL + REST"]
    external["Internet Public APIs\nOpen-Meteo & Apple iTunes"]

    user -->|"gửi câu hỏi chat (Element Web)"| agent
    agent -->|"gọi tool get_weather / search_music (MCP over SSE)"| system
    system -->|"truy vấn dữ liệu thực tế (HTTPS REST)"| external
    external -->|"trả dữ liệu thô (JSON)"| system
    system -->|"trả dữ liệu có cấu trúc"| agent
    agent -->|"soạn và trả lời kèm link audio preview"| user
```

**Ranh giới:** Giao diện chat (Element Web) và Matrix Synapse đóng vai trò hạ tầng kênh chat (Chat Platform). Report này tập trung vào chuỗi pipeline Gateway cung cấp dữ liệu thực tế cho OpenClaw Agent.

---

## 3. C2 — Container Diagram

```mermaid
flowchart LR
    caller["OpenClaw Gateway\nDocker Container · :18789"]

    subgraph gateway["Hệ thống Gateway (my-mcp-server)"]
      mcp["MCP Service\nPython MCPServer / FastMCP\n:8005 host\n/sse"]
      gql["GraphQL Service\nFastAPI + Strawberry\n:8002 host\n/graphql"]
      rest["REST Service\nFastAPI\n:8001 host\n/api/weather, /api/music, /docs"]
    end

    subgraph internet["Internet Public APIs"]
      meteo["Open-Meteo API\nGeocoding & Forecast"]
      itunes["Apple iTunes Search API\nSong search & 30s audio preview"]
    end

    caller -->|"gọi tool qua SSE (JSON-RPC)"| mcp
    mcp -->|"thực thi query (GraphQL/HTTP POST)"| gql
    gql -->|"lấy thời tiết / bài hát (REST/HTTP GET)"| rest
    rest -->|"lấy tọa độ & dự báo thời tiết (HTTPS GET)"| meteo
    rest -->|"tìm kiếm bài hát theo từ khóa (HTTPS GET)"| itunes
    meteo -->|"trả JSON thời tiết"| rest
    itunes -->|"trả JSON bài hát"| rest
    rest -->|"trả REST Response Model"| gql
    gql -->|"trả GraphQL result"| mcp
    mcp -->|"trả tool result text"| caller
```

| Container | Trách nhiệm chính | Giao tiếp ra ngoài |
|---|---|---|
| **OpenClaw Gateway** | Chạy AI Agent (GPT-4o-mini), lắng nghe tin nhắn Matrix và gọi MCP tool | MCP service qua SSE (`http://host.docker.internal:8005/sse`) |
| **MCP Service** | Expose các tool `get_weather(city)`, `search_music(query, limit)` theo chuẩn MCP | GraphQL service qua HTTP POST (`/graphql`) |
| **GraphQL Service** | Định nghĩa schema thống nhất (`Weather`, `MusicTrack`), gom nguồn dữ liệu REST | REST service qua HTTP GET |
| **REST Service** | Validate dữ liệu Pydantic, gọi Public APIs Open-Meteo và Apple iTunes | Internet APIs qua HTTPS |

---

## 4. C3 — Component Diagram (MCP Service)

```mermaid
flowchart TB
    client["MCP client\n(OpenClaw Gateway)"]

    subgraph mcp["mcp_server/ (server.py)"]
      transport["SSE Transport\nMCPServer('RealDataMCP')\n:8005/sse"]
      tools["MCP Tools\n- get_weather(city)\n- search_music(query, limit)"]
      gqlhelper["gql() Helper\nrequests.post /graphql\ntimeout 15s"]
    end

    gql["GraphQL API\ngraphql_server/ (:8002)"]

    client -->|"kết nối & gọi tool (JSON-RPC qua SSE)"| transport
    transport -->|"route tool invocation"| tools
    tools -->|"gọi query tương ứng"| gqlhelper
    gqlhelper -->|"gửi query + variables (HTTP POST /graphql)"| gql
    gql -->|"trả data/errors (JSON)"| gqlhelper
    gqlhelper -->|"trả data dict"| tools
    tools -->|"format kết quả dạng text"| transport
    transport -->|"phản hồi kết quả tool"| client
```

**Điểm cần lưu ý trong C3:**
- Hàm `gql()` có timeout 15 giây và raise `RuntimeError` khi GraphQL trả về field `errors`.
- Tool `search_music` hỗ trợ tham số mặc định `limit = 3` nếu caller không chỉ định số lượng.
- Khi khởi động lại MCP Service, caller cần thực hiện lại bắt tay `initialize` để tránh mã lỗi `-32602` (`INVALID_PARAMS`).

---

## 5. Sequence 1 — Tra cứu thời tiết

Ví dụ câu hỏi: “Thời tiết ở Đà Nẵng như nào?”. Tool tương ứng: `get_weather(city="Đà Nẵng")`.

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant A as OpenClaw / Agent
    participant M as MCP Service (:8005)
    participant G as GraphQL Service (:8002)
    participant R as REST Service (:8001)
    participant O as Open-Meteo API

    U->>A: hỏi thời tiết "Đà Nẵng"
    A->>M: get_weather("Đà Nẵng") (MCP/SSE)
    M->>G: query weather(city: "Đà Nẵng") (GraphQL/HTTP POST)
    G->>R: GET /api/weather?city=Đà%20Nẵng (REST)
    R->>O: GET geocoding tìm tọa độ + forecast lấy thời tiết (HTTPS)
    O-->>R: trả tọa độ, nhiệt độ, độ ẩm, gió (JSON)
    R-->>G: trả WeatherResponse {city, temperature, humidity, wind_speed} (JSON)
    G-->>M: trả weather result (GraphQL JSON)
    M-->>A: trả text "Đà Nẵng: 30.4°C, độ ẩm 71%, gió 8.4 km/h" (MCP)
    A-->>U: trả lời thông tin thời tiết định dạng Markdown
```

---

## 6. Sequence 2 — Tìm kiếm bài hát theo số lượng

Ví dụ câu hỏi: “5 bài nhạc của Đen Vâu”. Tool tương ứng: `search_music(query="Đen Vâu", limit=5)`.

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant A as OpenClaw / Agent
    participant M as MCP Service (:8005)
    participant G as GraphQL Service (:8002)
    participant R as REST Service (:8001)
    participant I as Apple iTunes API

    U->>A: hỏi "5 bài nhạc của Đen Vâu"
    A->>M: search_music(query="Đen Vâu", limit=5) (MCP/SSE)
    M->>G: query searchMusic(query: "Đen Vâu", limit: 5) (GraphQL/HTTP POST)
    G->>R: GET /api/music?query=Đen%20Vâu&limit=5 (REST)
    R->>I: GET search term="Đen Vâu", entity="song", country="VN", limit=5 (HTTPS)
    I-->>R: trả danh sách results (JSON)
    alt Có bài hát tìm thấy
        R-->>G: trả List[MusicTrackResponse] (JSON)
        G-->>M: trả searchMusic result (GraphQL JSON)
        M-->>A: trả danh sách bài hát kèm link audio preview (MCP text)
        A-->>U: trả lời danh sách bài hát kèm link [Nghe bài hát]
    else Không tìm thấy bài nào
        R-->>G: trả list rỗng [] (JSON)
        G-->>M: trả searchMusic: [] (GraphQL JSON)
        M-->>A: trả "Không tìm thấy bài nào." (MCP text)
        A-->>U: thông báo chưa tìm thấy bài hát phù hợp
    end
```

---

## 7. Ghi chú vận hành và giới hạn hiện tại

- **Chuỗi gọi đồng bộ:** OpenClaw ➡️ MCP ➡️ GraphQL ➡️ REST ➡️ Public APIs; toàn bộ thực thi theo mô hình request-response đồng bộ, không sử dụng message broker hay caching.
- **Cấu hình Endpoint:** `GRAPHQL_URL` và `REST_API_URL` hiện trỏ trực tiếp loopback `http://127.0.0.1`. Khi container hóa toàn bộ hệ thống bằng Docker Compose, các URL này có thể được chuyển sang sử dụng biến môi trường (`os.getenv`).
- **Xử lý số lượng bài hát:** `search_music` tự động fallback về `limit = 3` nếu prompt của người dùng không chứa số lượng bài cụ thể; API iTunes được cấu hình mặc định vùng Việt Nam (`country="VN"`).
- **Endpoint kiểm tra (Health & Docs):** 
  - REST Service: Swagger UI tại `http://127.0.0.1:8001/docs`.
  - GraphQL Service: Interactive GraphQL Playground tại `http://127.0.0.1:8002/graphql`.
  - MCP Service: SSE stream lắng nghe tại `http://0.0.0.0:8005/sse`.
