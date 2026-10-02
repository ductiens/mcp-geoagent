# Kết nối OpenClaw với Synapse và MCP

**Phần con của Agent Stack document: chi tiết hóa mục 5 (Bước 2, dựng OpenClaw) và bước 4 của mục 6.1 (khai MCP vào OpenClaw)**

**Đọc xong bạn sẽ:**

* Tạo được tài khoản bot trên Synapse và cho OpenClaw đăng nhập bằng tài khoản đó.
* Chạy được OpenClaw trong Docker, nhắn tin trong Element và nhận bot trả lời.
* Khai được MCP server vào OpenClaw, thấy bot gọi tool và trả lời bằng dữ liệu thật.
* Biết kiểm tra từng chặng khi có lỗi, thay vì đoán.

Các giá trị trong dấu `<...>` là giá trị bạn tự điền. Chúng là bí mật, **không commit** lên repo.

Đăng nhập SSO bằng Keycloak (Bài 3) và tracing (Bài 4) có hướng dẫn riêng trong tài liệu chính. Phần này chạy được khi chưa có hai bài đó.


---

## 1. Bức tranh kết nối

OpenClaw chạy trong một container Docker riêng. Synapse chạy trong container khác. MCP server chạy trực tiếp trên máy host. Ba thứ này nói chuyện với nhau qua mạng, nên **địa chỉ phải đúng theo góc nhìn của bên đi gọi**.

```
 MÁY HOST
 ┌─────────────────────────────────────────────────────────────┐
 │                                                             │
 │   Element :8080 ────▶ Synapse :8008 (container)             │
 │                            ▲                                │
 │                            │ Matrix API                     │
 │   ┌────────────────────────┴──────────────────┐             │
 │   │ openclaw-box (container)                  │──▶ LLM      │
 │   │ OpenClaw Gateway                          │   (HTTPS)   │
 │   └────────────────────────┬──────────────────┘             │
 │                            │ MCP (Streamable HTTP)          │
 │                            ▼                                │
 │   MCP Server :8005 (chạy trực tiếp trên host)               │
 │                                                             │
 └─────────────────────────────────────────────────────────────┘
```

* **Synapse**: nhận và phân phối tin nhắn. Bot cũng chỉ là một tài khoản Matrix bình thường.
* **OpenClaw Gateway**: đăng nhập Synapse bằng tài khoản bot, nhận tin nhắn, hỏi LLM, gọi tool MCP, trả lời vào phòng.
* **MCP server**: cung cấp tool cho bot. Bên trong gọi GraphQL (Bài 1).

### 1.1. Địa chỉ nhìn từ đâu

Bên trong container, `localhost` và `127.0.0.1` là **chính container đó**, không phải máy host. Container muốn gọi ra máy host phải dùng `host.docker.internal`.

| Bên gọi | Bên được gọi | Địa chỉ dùng |
|---------|--------------|--------------|
| Trình duyệt (Element) | Synapse | `http://localhost:8008` |
| OpenClaw (trong container) | Synapse | `http://host.docker.internal:8008` |
| OpenClaw (trong container) | MCP server | `http://host.docker.internal:8005/mcp` |
| MCP server (trên host) | GraphQL | `http://127.0.0.1:<cổng GraphQL>/graphql` |

Tài liệu chính ghi Synapse là `http://localhost:8008`. Đó là địa chỉ nhìn từ máy host và trình duyệt. Riêng OpenClaw chạy trong container thì dùng `http://host.docker.internal:8008`. Hai cách ghi này cùng trỏ tới một Synapse.

### 1.2. Hai quy tắc về mạng

* Dịch vụ trên host mà container cần gọi (MCP) phải lắng nghe ở **`0.0.0.0`**. Nếu chỉ lắng nghe `127.0.0.1` thì chỉ tiến trình trên host kết nối được, container gọi vào sẽ bị `Connection refused`.
* Container cần `--add-host=host.docker.internal:host-gateway` để phân giải tên `host.docker.internal`. Docker Desktop thường có sẵn, nhưng thêm cờ này cho chắc, không có hại.


---

## 2. Điều kiện trước

- [ ] Bước 1 đã xong: Synapse chạy ở cổng `8008`, đăng nhập được Element bằng tài khoản test.
- [ ] Docker đang chạy.
- [ ] Có API key của LLM, hoặc endpoint LLM do người phụ trách cấp. Hướng dẫn này dùng OpenAI `gpt-4o-mini`.
- [ ] Biết thư mục dữ liệu Synapse (`~/synapse-data`, nơi có `homeserver.yaml`).

Cổng của MCP, GraphQL, REST do bạn chọn và ghi vào README của bài (theo bảng cổng của tài liệu chính). Hướng dẫn này dùng MCP ở cổng `8005`.


---

## 3. Tạo tài khoản bot trên Synapse

OpenClaw cần một tài khoản riêng trên Synapse để đăng nhập và chat. Tài khoản này **không cần quyền admin**.

```bash
docker exec synapse register_new_matrix_user -u openclaw -p <BOT_PASSWORD> --no-admin -c /data/homeserver.yaml http://localhost:8008
```

Kết quả: tài khoản Matrix `@openclaw:localhost`.

* `-c /data/homeserver.yaml`: lệnh đọc `registration_shared_secret` từ file này để được phép tạo tài khoản.
* Đặt mật khẩu mạnh, khác mật khẩu mẫu trong tài liệu. Chỉ dùng mật khẩu đơn giản khi test trên máy cá nhân.
* Tên `openclaw` đã dùng cho bot. Ở Bài 3, đừng tạo user Keycloak trùng tên này, nếu không đăng nhập SSO lần đầu sẽ báo trùng tài khoản.

Việc kiểm tra tài khoản đăng nhập được làm ở mục 4.3, sau khi có container OpenClaw.


---

## 4. Dựng container OpenClaw

### 4.1. Tạo container

```bash
docker run -d --name openclaw-box --add-host=host.docker.internal:host-gateway -v openclaw-data:/root/.openclaw -it node:22-bookworm bash
```

* `--add-host=host.docker.internal:host-gateway`: để container gọi được máy host.
* `-v openclaw-data:/root/.openclaw`: giữ cấu hình khi xóa và tạo lại container. Không có dòng này, `docker rm` là mất toàn bộ cấu hình OpenClaw.
* `node:22-bookworm`: OpenClaw chạy trên Node.js.

### 4.2. Cài OpenClaw

```bash
docker exec -it openclaw-box bash
npm install -g openclaw@2026.4.2
openclaw --version
```

Cài **đúng một phiên bản cụ thể** (ở đây là `2026.4.2`, bản đã test) và ghi vào README của dự án. Dùng `@latest` thì mỗi người cài một bản khác nhau, tên cấu hình có thể khác, tài liệu này sẽ không còn đúng.

### 4.3. Kiểm tra container gọi được Synapse

Ở lại trong shell của container (`docker exec -it openclaw-box bash`) và chạy:

```bash
curl -s http://host.docker.internal:8008/_matrix/client/versions
```

Trả về JSON có danh sách `versions` là mạng thông. Tiếp theo kiểm tra tài khoản bot:

```bash
curl -s -X POST http://host.docker.internal:8008/_matrix/client/v3/login \
  -H "Content-Type: application/json" \
  -d '{"type":"m.login.password","user":"openclaw","password":"<BOT_PASSWORD>"}'
```

Kết quả đúng có `access_token` và `"user_id":"@openclaw:localhost"`.

| Kết quả | Nghĩa là |
|---------|----------|
| `Could not resolve host` | Container thiếu `--add-host`. Tạo lại container theo 4.1 |
| `Connection refused` hoặc treo | Synapse chưa chạy hoặc chưa map cổng `8008` ra máy host |
| `M_FORBIDDEN` | Sai tên hoặc mật khẩu bot. Kiểm tra lại mục 3 |

### 4.4. Xong mục 4 khi

- [ ] `openclaw --version` in ra đúng phiên bản đã chọn.
- [ ] `curl` từ trong container tới Synapse trả JSON.
- [ ] Đăng nhập bot bằng `curl` nhận được `access_token`.


---

## 5. Cấu hình OpenClaw

Cấu hình nằm ở `/root/.openclaw/openclaw.json` trong container. Soạn file trên máy host (ví dụ `openclaw.json` trong thư mục dự án, đã thêm vào `.gitignore`), rồi chép vào container:

```bash
docker cp openclaw.json openclaw-box:/root/.openclaw/openclaw.json
```

### 5.1. Nội dung `openclaw.json` (chưa có MCP)

Phần MCP thêm ở mục 8, để từng chặng được kiểm tra riêng.

```json
{
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "apiKey": "<OPENAI_API_KEY>",
        "api": "openai-completions",
        "models": [
          { "id": "gpt-4o-mini", "name": "gpt-4o-mini" }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": { "primary": "openai/gpt-4o-mini" }
    }
  },
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "auth": { "mode": "token", "token": "<GATEWAY_TOKEN>" }
  },
  "channels": {
    "matrix": {
      "enabled": true,
      "homeserver": "http://host.docker.internal:8008",
      "userId": "@openclaw:localhost",
      "password": "<BOT_PASSWORD>",
      "deviceName": "OpenClaw Docker Box",
      "encryption": true,
      "autoJoin": "always",
      "dm": { "policy": "open", "allowFrom": ["*"] },
      "groupPolicy": "open",
      "allowPrivateNetwork": true
    }
  },
  "plugins": {
    "entries": { "matrix": { "enabled": true } }
  },
  "tools": {
    "web": { "search": { "enabled": false } }
  }
}
```

Cấu hình này đã chạy được với phiên bản OpenClaw ghi ở mục 4.2. Tên khóa có thể khác giữa các phiên bản, nên nếu bản bạn cài báo lỗi, kiểm tra bằng `openclaw config validate` và hỏi người phụ trách.

### 5.2. Giải thích các khối

| Khóa | Ý nghĩa |
|------|---------|
| `models`, `agents.defaults.model` | LLM mà bot dùng để hiểu câu hỏi và soạn câu trả lời |
| `gateway.bind: "loopback"` | Cổng điều khiển của gateway chỉ mở trong container, không mở ra ngoài |
| `gateway.auth.token` | Token bảo vệ cổng điều khiển. Tự sinh một chuỗi ngẫu nhiên, không dùng giá trị mẫu |
| `channels.matrix.homeserver` | Địa chỉ Synapse **nhìn từ trong container**, nên là `host.docker.internal`, không phải `localhost` |
| `userId`, `password` | Tài khoản bot đã tạo ở mục 3 |
| `deviceName` | Tên thiết bị bot hiển thị trên Matrix |
| `encryption` | Cho phép bot xử lý phòng mã hóa E2EE. Xem lưu ý bên dưới |
| `autoJoin: "always"` | Được mời vào phòng là bot tự nhận lời mời |
| `dm.policy`, `groupPolicy: "open"` | Ai cũng nhắn được bot. Chỉ phù hợp khi chạy local (xem mục 10) |
| `allowPrivateNetwork` | Cho phép kết nối tới Synapse ở địa chỉ mạng nội bộ |
| `tools.web.search.enabled: false` | Tắt tìm kiếm web, để bot trả lời bằng dữ liệu từ tool MCP thay vì tự tìm ngoài |

**Về mã hóa E2EE:** bot chỉ đọc được tin nhắn trong phòng mã hóa khi nhận được khóa phòng từ thiết bị khác. Khi mới làm, **tạo phòng test không bật mã hóa** (xem mục 7) để loại bỏ yếu tố này.

### 5.3. Kiểm tra cấu hình

```bash
docker exec openclaw-box openclaw config validate
```

Kết quả hợp lệ có dạng `Config valid: ~/.openclaw/openclaw.json`. Luôn chạy lệnh này sau mỗi lần sửa cấu hình, trước khi khởi động lại gateway.


---

## 6. Chạy OpenClaw Gateway

Gateway là tiến trình thường trực: đăng nhập Synapse, nhận tin nhắn, gọi LLM và tool.

### 6.1. Khởi động

```bash
docker exec openclaw-box pkill -f openclaw-gateway
docker exec -d openclaw-box bash -c "openclaw gateway run > /tmp/openclaw.log 2>&1"
```

Dòng đầu dừng tiến trình cũ (báo lỗi "không có tiến trình nào" là bình thường nếu chưa chạy lần nào). Dòng sau chạy gateway ở chế độ nền, ghi log ra `/tmp/openclaw.log`.

### 6.2. Xem log

```bash
docker exec openclaw-box tail -f /tmp/openclaw.log
```

Log chi tiết theo ngày (sự kiện Matrix, tool call):

```bash
docker exec openclaw-box bash -c 'tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log'
```

### 6.3. Kiểm tra gateway đang chạy

```bash
docker exec openclaw-box bash -c "ps aux | grep openclaw-gateway"
```

### 6.4. Lưu ý

* Gateway chạy bằng `docker exec -d` nên **mất khi container khởi động lại** (tắt máy, `docker restart`). Phải chạy lại lệnh ở 6.1.
* Cấu hình không mất nhờ volume `openclaw-data` (mục 4.1).


---

## 7. Mời bot vào phòng và kiểm tra

### 7.1. Tạo phòng test

1. Mở Element (`http://localhost:8080`), đăng nhập bằng tài khoản test.
2. Tạo phòng mới. **Tắt công tắc *Enable end-to-end encryption*** khi tạo. Matrix không cho tắt mã hóa sau khi đã bật, nên phải tắt ngay lúc tạo.
3. Mời `@openclaw:localhost` vào phòng. Nhờ `autoJoin: "always"`, bot tự vào.
4. Gửi một tin, ví dụ "Xin chào".

Bot trả lời trong vài giây là OpenClaw đã nối thông Synapse và LLM.

### 7.2. Nếu bot không trả lời

Kiểm tra theo thứ tự, mỗi bước loại một chặng:

| # | Kiểm tra | Cách làm |
|---|----------|----------|
| 1 | Gateway có chạy không | Lệnh ở 6.3 |
| 2 | Bot có trong phòng không | Xem danh sách thành viên phòng trong Element |
| 3 | Bot có nhận được tin không | Xem log (6.2), tìm sự kiện tin nhắn mới |
| 4 | LLM có trả lời không | Xem log có lỗi gọi `api.openai.com` không (sai API key, hết quota, không ra được Internet) |

### 7.3. Persona của bot

Tính cách và vai trò của bot nằm trong các file của workspace OpenClaw (`IDENTITY.md`, `SOUL.md`, `AGENTS.md`, `USER.md`, xem mục 5 của tài liệu chính). Để bot chỉ trả lời bằng dữ liệu thật, nên ghi rõ trong persona: **dữ liệu lấy từ tool, không có dữ liệu thì nói không có, không tự bịa**. Vị trí thư mục workspace phụ thuộc phiên bản, hỏi người phụ trách nếu chưa thấy.

### 7.4. Xong Bước 2 khi

- [ ] Gateway chạy, log không có lỗi đỏ.
- [ ] Bot đã join phòng test.
- [ ] Nhắn trong Element, bot trả lời.


---

## 8. Kết nối MCP

Làm theo thứ tự: dựng một MCP server **tối thiểu** với một tool đơn giản, nối vào OpenClaw và kiểm tra bot gọi được. Khi chặng này chắc chắn thông, Bài 1 chỉ việc thay phần bên trong tool bằng lời gọi GraphQL.

### 8.1. Yêu cầu với MCP server

* Dùng **Streamable HTTP**, không dùng SSE (theo yêu cầu của Bài 1).
* Lắng nghe ở **`0.0.0.0`** để container gọi được (mục 1.2).
* Biết đúng **path** server phục vụ (thường là `/mcp`) và khai đúng path đó, kể cả dấu `/` cuối. Lệch dấu `/` sẽ bị `307 Temporary Redirect` ở mỗi request.
* Ghim phiên bản thư viện `mcp` trong `requirements.txt`. Tên import và cách khai báo server thay đổi giữa các phiên bản SDK.

### 8.2. MCP server tối thiểu

```python
from mcp.server.mcpserver import MCPServer  # tên import theo phiên bản SDK đã ghim

mcp = MCPServer("MyMCP")


@mcp.tool()
def ping(name: str) -> str:
    """Kiểm tra kết nối MCP. Gọi tool này khi người dùng yêu cầu 'ping' hoặc
    'kiểm tra kết nối', truyền tên người dùng vào tham số name."""
    return f"pong, xin chào {name}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8005)
```

Chạy từ thư mục dự án:

```bash
python -m mcp_server.server
```

### 8.3. Kiểm tra mạng từng chặng

Kiểm tra từ máy host trước, rồi từ trong container. Hai kết quả giống nhau nghĩa là mạng thông.

```bash
# Trên máy host
curl -i http://localhost:8005/mcp

# Từ container
docker exec openclaw-box curl -i http://host.docker.internal:8005/mcp
```

Phản hồi HTTP bất kỳ (kể cả mã 4xx như 400, 405, 406, vì lệnh `curl` này không phải một request MCP đúng chuẩn) là **mạng đã thông**. Chỉ cần thấy server trả lời.

| Kết quả | Nghĩa là |
|---------|----------|
| Host được, container `Connection refused` | Server đang bind `127.0.0.1`. Đổi sang `0.0.0.0` |
| Host được, container treo hoặc timeout | Windows Firewall chặn cổng `8005`. Tạo Inbound Rule cho cổng này |
| Container `Could not resolve host` | Thiếu `--add-host` (mục 4.1) |
| Cả hai đều lỗi | MCP server chưa chạy, hoặc sai cổng |

### 8.4. Khai MCP vào OpenClaw

Thêm khối `mcp` vào `openclaw.json`:

```json
"mcp": {
  "servers": {
    "my_mcp": {
      "url": "http://host.docker.internal:8005/mcp",
      "transport": "streamable-http"
    }
  }
}
```

**Bắt buộc khai `"transport": "streamable-http"`.** OpenClaw không tự nhận kiểu transport theo URL. Nếu bỏ trống khóa này, OpenClaw mặc định coi server là `sse`, nên kết nối vào endpoint `/mcp` sẽ thất bại. (Đã kiểm tra trên OpenClaw `2026.4.2`.)

Sau khi sửa:

```bash
docker cp openclaw.json openclaw-box:/root/.openclaw/openclaw.json
docker exec openclaw-box openclaw config validate
docker exec openclaw-box pkill -f openclaw-gateway
docker exec -d openclaw-box bash -c "openclaw gateway run > /tmp/openclaw.log 2>&1"
```

* `my_mcp` là tên bạn đặt cho MCP server. OpenClaw thêm tên này làm tiền tố cho tool, ví dụ `my_mcp__ping`.
* Sửa code MCP (thêm tool, đổi docstring) thì **khởi động lại MCP server rồi khởi động lại gateway**, vì OpenClaw chỉ lấy danh sách tool lúc kết nối.

### 8.5. Kiểm tra bot gọi được tool

Trong phòng test, nhắn: "Ping giúp tôi, tên tôi là Lan".

Quan sát:

1. **Log OpenClaw**: có tool call `my_mcp__ping` kèm `{"name": "Lan"}`.
2. **Terminal MCP server**: có request tới. Không có request nào nghĩa là bot không gọi tool.
3. **Element**: bot trả lời có câu "pong, xin chào Lan".

### 8.6. Viết docstring cho tool

LLM chọn tool dựa vào tên và docstring (đây là trường `description` mà MCP gửi sang). Docstring mơ hồ hoặc để trống thì bot không biết khi nào gọi và tự trả lời bằng kiến thức của nó. Một docstring tốt nói rõ 3 ý:

* Tool làm gì.
* Gọi khi nào (kèm ví dụ câu hỏi của người dùng).
* Ý nghĩa từng tham số.

```python
@mcp.tool()
def get_tasks(assignee: str, status: str = "open") -> str:
    """Lấy danh sách công việc theo người được giao và trạng thái.
    Gọi tool này khi người dùng hỏi về công việc của một người,
    ví dụ "task của Lan còn mấy việc chưa xong?".

    Args:
        assignee: Tên người được giao việc, ví dụ "Lan".
        status: Trạng thái công việc, "open" hoặc "done".
    """
```

### 8.7. Khi chuyển sang Bài 1

Thay thân hàm tool bằng lời gọi GraphQL (MCP chỉ gửi query, không tự lấy dữ liệu, nghiệp vụ nằm ở REST). Mỗi tầng đặt timeout, và **timeout của tầng trên phải lớn hơn tầng dưới**, nếu không tầng trên bỏ cuộc trước khi tầng dưới kịp trả lời:

| Chặng | Gợi ý timeout |
|-------|---------------|
| REST → nguồn dữ liệu (DB hoặc API bên ngoài) | 10 giây |
| GraphQL → REST | 15 giây |
| MCP → GraphQL | 25 giây |

Khi gặp lỗi (không tìm thấy dữ liệu, service phía sau lỗi), MCP nên trả về thông báo lỗi dễ hiểu thay vì để lỗi thô văng ra, để bot nói được với người dùng là không có dữ liệu.

### 8.8. Xong mục 8 khi

- [ ] `curl` từ host và từ container đều nhận được phản hồi HTTP từ MCP server.
- [ ] `openclaw config validate` hợp lệ sau khi thêm khối `mcp`.
- [ ] Hỏi bot, log OpenClaw hiện tool call và terminal MCP hiện request tương ứng.
- [ ] Bot trả lời bằng kết quả của tool.


---

## 9. Kịch bản kiểm thử toàn luồng

Chạy sau khi Bài 1 đã thay `ping` bằng tool thật (ví dụ `get_tasks`). Dùng phòng test không mã hóa. Các tình huống này nối tiếp checklist ở mục 8.3 của tài liệu chính.

| # | Việc làm | Kết quả đúng |
|---|----------|--------------|
| 1 | Hỏi câu có dữ liệu thật (ví dụ "Task của Lan còn mấy việc chưa xong?") | Bot gọi tool, trả số liệu khớp với kết quả gọi trực tiếp REST |
| 2 | Hỏi câu cần dữ liệu từ cả 2 REST API (ví dụ danh sách task kèm tên người phụ trách) | Bot trả lời đủ thông tin từ cả hai nguồn |
| 3 | Hỏi câu **không có** dữ liệu (ví dụ người không tồn tại) | Bot nói không có dữ liệu, không bịa |
| 4 | Tắt MCP server rồi hỏi lại | Bot báo không lấy được dữ liệu, không bịa |
| 5 | Bật lại MCP server, khởi động lại gateway, hỏi lại | Bot hoạt động bình thường trở lại |

Trong lúc chạy, theo dõi log theo luồng: tin nhắn Matrix → tool call (OpenClaw) → request (MCP) → query (GraphQL) → request (REST). Chặng nào không thấy log là chỗ đứt.


---

## 10. An toàn khi chạy local

| Việc | Lý do |
|------|-------|
| Không commit `openclaw.json`, `homeserver.yaml`, `.env`. Thêm vào `.gitignore` | Chứa API key, mật khẩu bot, token gateway |
| Ghi giá trị mẫu dạng `<...>` trong tài liệu và README | Người đọc không thấy bí mật thật, và biết phải tự điền |
| Nếu từng lộ API key, token hoặc mật khẩu (dán vào chat, commit nhầm) thì **tạo lại** | Xóa khỏi file không đủ, vì giá trị cũ đã bị lộ |
| Bot không có quyền admin trên Synapse | Bot bị lợi dụng thì thiệt hại hạn chế |
| `dm.policy: open` và `groupPolicy: open` chỉ dùng khi chạy local | Cấu hình này cho **bất kỳ ai** nhắn được bot. Triển khai thật phải giới hạn người được dùng |
| Khi làm Bài 3, **không tắt đăng nhập bằng mật khẩu** trên Synapse | Bot vẫn đăng nhập bằng mật khẩu |


---

## 11. Sự cố thường gặp

Bảng này bổ sung vào bảng "Element, Synapse, OpenClaw, MCP" ở mục 12 của tài liệu chính.

| Triệu chứng | Nguyên nhân và cách xử lý |
|-------------|---------------------------|
| `Could not resolve host: host.docker.internal` | Container thiếu `--add-host=host.docker.internal:host-gateway`. Tạo lại container theo mục 4.1 |
| Bot không trả lời trong phòng | Làm theo bảng ở mục 7.2: gateway, bot có trong phòng, log nhận tin, lỗi LLM |
| Log hiện `DecryptionError: The sender's device has not sent us the keys for this message` | Phòng bật mã hóa E2EE nhưng bot chưa nhận được khóa phòng. Tạo phòng test mới và tắt mã hóa khi tạo |
| `config validate` báo lỗi | Sai cú pháp JSON hoặc khác tên khóa so với phiên bản OpenClaw. Đọc dòng lỗi, đối chiếu phiên bản đã cài |
| Log OpenClaw báo không kết nối được MCP (`fetch failed`, `Connection refused`) | Theo bảng ở mục 8.3: MCP chưa chạy, bind `127.0.0.1`, hoặc Firewall chặn cổng `8005` |
| MCP chạy, mạng thông, nhưng OpenClaw vẫn không kết nối được `/mcp` | Thiếu `"transport": "streamable-http"` trong khối `mcp.servers` nên OpenClaw dùng `sse`. Thêm khóa này (mục 8.4) |
| Log MCP hiện `307 Temporary Redirect` ở mỗi request | Địa chỉ MCP khai trong OpenClaw lệch dấu `/` cuối so với path server phục vụ. Sửa lại địa chỉ |
| Sửa code MCP nhưng bot vẫn dùng bản cũ | OpenClaw lấy danh sách tool lúc kết nối. Khởi động lại MCP server, rồi khởi động lại gateway |
| Bot chat bình thường nhưng không gọi tool | Docstring mơ hồ hoặc trống. Viết lại theo mục 8.6 |
| Lỗi tool `-32602: Client must be initialized before calling tools` | Thường xảy ra sau khi MCP server khởi động lại, mất phiên làm việc cũ. Khởi động lại gateway để OpenClaw tạo phiên mới. Nếu vẫn lặp lại, ghi lại phiên bản `mcp` và OpenClaw rồi báo người phụ trách |
| `Read timed out` | Service phía sau (REST, GraphQL, API bên ngoài) trả lời chậm. Tăng timeout theo bảng ở mục 8.7 |
| Khởi động lại máy hoặc container xong bot im lặng | Gateway chạy bằng `docker exec -d` nên đã dừng. Chạy lại lệnh ở mục 6.1 |
| Xóa container xong mất cấu hình | Chưa gắn volume `openclaw-data`. Tạo lại container có `-v` rồi cấu hình lại |


---

## 12. Vị trí trong Agent Stack document

| Mục của phần này | Ghép vào tài liệu chính |
|------------------|-------------------------|
| 1. Bức tranh kết nối | Mục 1 (bổ sung chi tiết đường OpenClaw ↔ Synapse, OpenClaw ↔ MCP) |
| 2 đến 7, và 10 | Mục 5, Bước 2: bổ sung vào chỗ "Cách cài đặt và cấu hình OpenClaw" |
| 8. Kết nối MCP | Mục 6.1, bước 4 |
| 9. Kịch bản kiểm thử | Mục 8.3 |
| 11. Sự cố thường gặp | Mục 12, bảng "Element, Synapse, OpenClaw, MCP" |
