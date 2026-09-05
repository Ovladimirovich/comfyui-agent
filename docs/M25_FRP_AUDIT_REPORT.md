# M25 Remote Transport Audit — Oracle VPS + FRP

**Статус:** AUDIT ONLY — no code changes
**Дата:** 2026-09-04
**Цель:** Определить минимальную точку интеграции FRP для стабильного remote ComfyUI

---

## A. CURRENT REMOTE PATH

```
Environment Variable
  COMFY_REMOTE_URL = "https://xxx.trycloudflare.com"
        │
        ▼
  BackendCatalog.from_env()
  → BackendSpec(backend_id="remote_comfyui", base_url=url, priority=10)
        │
        ▼
  Agent.prepare(capability, provider=..., base_url=url)
  → _build_provider(backend_id, base_url=url)
  → ComfyClient(base_url=url, timeout=60)
        │
        ├─── HTTP: POST /prompt, GET /history, POST /upload/image
        │
        └─── WS:  wss://{host}/ws?client_id=xxx
                ↑
        ComfyUIWebSocket.__init__ extracts scheme from base_url
        https → wss://   http → ws://
        │
        ▼
  ComfyUIProvider(client, backend_id="remote_comfyui")
        │
        ├─── upload_asset() → client.upload_image()
        ├─── execute() → client.queue_prompt()
        ├─── get_job() → client.get_history()
        └─── view() → client.view()
        │
        ▼
  WorkflowEngine.execute(manifest, plan, provider)
  → build_prompt() → _bind_models() → provider.execute()
  → ws.track() → fallback /history → Verifier → AssetStore
```

**Ключевые выводы:**

1. **Компонент, зависящий от URL:** только `ComfyClient` (transport layer)
2. **Абстракция backend:** `backend_id` + `base_url` — уже параметризованы
3. **WebSocket:** автоматически выбирает ws/wss по scheme base_url
4. **Provider/Backend boundary:** существует с M5, remote уже first-class citizen (AD-29)
5. **M20 Gateway:** опционален, ConversationAgent НЕ использует его напрямую

---

## B. FRP INTEGRATION POINT

### Где интегрировать

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Host (Windows)                                        │
│                                                              │
│  COMFY_REMOTE_URL = "http://VPS_PUBLIC_IP:7000"             │
│        │                                                     │
│        ▼                                                     │
│  ComfyClient("http://VPS_PUBLIC_IP:7000")                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ HTTP:  http://VPS:7000/prompt                        │   │
│  │ WS:    ws://VPS:7000/ws?client_id=...                │   │
│  │ Upload: http://VPS:7000/upload/image                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                     TCP Tunnel (FRP)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Oracle Cloud VPS (frps)                                    │
│                                                              │
│  frps --config frps.toml                                     │
│    bind_port = 7000                                          │
│    dashboard_port = 7500 (опц.)                              │
│                                                              │
│  Firewall: open TCP 7000, 7500 (опц.)                        │
└─────────────────────────────────────────────────────────────┘
                          │
                     TCP Tunnel (FRP)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Colab Runtime (frpc)                                       │
│                                                              │
│  !wget https://github.com/fatedier/frp/releases/...         │
│  !tar zxvf frpc_*.tar.gz                                     │
│  !./frpc -c frpc.toml &                                      │
│                                                              │
│  frpc.toml:                                                  │
│    server_addr = "VPS_PUBLIC_IP"                             │
│    server_port = 7000                                        │
│    auth.token = "SECRET"                                     │
│                                                              │
│  [comfyui]                                                   │
│    type = tcp                                                │
│    local_ip = 127.0.0.1                                      │
│    local_port = 8188                                         │
│    remote_port = 7000                                        │
│                                                              │
│  ComfyUI --listen 0.0.0.0 --port 8188                        │
└─────────────────────────────────────────────────────────────┘
```

**Точка интеграции:** единственная переменная — `COMFY_REMOTE_URL`.
FRP прозрачен для Agent — он работает на уровне TCP.

---

## C. REQUIRED VPS CONFIG

### Oracle Cloud Free Tier VPS

| Параметр | Значение |
|----------|----------|
| Instance | VM.Standard.A1.Flex (ARM, 1 GPU = opcional) |
| OS | Ubuntu 22.04 / Oracle Linux 9 |
| CPU | 4 OCPUs |
| RAM | 24 GB |
| Storage | 100 GB |
| Network | Public IP (free tier) |

### Ports

| Port | Protocol | Назначение |
|------|----------|------------|
| 7000 | TCP | FRP server bind port (основной) |
| 7500 | TCP | FRP dashboard (опционально) |
| 8188 | TCP | ComfyUI (локально, не对外开放) |

### Security Group (Oracle Cloud)

```
Inbound Rules:
  - TCP 7000  from 0.0.0.0/0  (FRP server)
  - TCP 7500  from 0.0.0.0/0  (dashboard, опц.)
  - TCP 22    from your IP     (SSH)
```

### FRP Server Config (frps.toml)

```toml
bindPort = 7000
token = "YOUR_SECRET_TOKEN"

# Optional: dashboard
webServer.addr = "0.0.0.0"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "YOUR_PASSWORD"
```

### Установка на VPS

```bash
# Download frp
wget https://github.com/fatedier/frp/releases/download/v0.60.0/frp_0.60.0_linux_arm64.tar.gz
tar zxvf frp_0.60.0_linux_arm64.tar.gz
cd frp_0.60.0_linux_arm64

# Create config
cat > frps.toml << 'EOF'
bindPort = 7000
token = "YOUR_SECRET_TOKEN"
webServer.addr = "0.0.0.0"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "YOUR_PASSWORD"
EOF

# Run as service
sudo cp frps /usr/local/bin/
sudo systemctl install frps.service
sudo systemctl enable frps
sudo systemctl start frps

# Verify
curl http://localhost:7500/api/info
```

---

## D. REQUIRED COLAB CONFIG

### Colab Setup (каждый запуск сессии)

```python
# Cell 1: Install frpc
!wget -q https://github.com/fatedier/frp/releases/download/v0.60.0/frp_0.60.0_linux_amd64.tar.gz
!tar zxvf frp_0.60.0_linux_amd64.tar.gz
!cp frp_0.60.0_linux_amd64/frpc /usr/local/bin/

# Cell 2: Start FRP client
import os
VPS_IP = "YOUR_VPS_PUBLIC_IP"
TOKEN = "YOUR_SECRET_TOKEN"

frpc_config = f"""
server_addr = "{VPS_IP}"
server_port = 7000
token = "{TOKEN}"

[comfyui]
type = tcp
local_ip = 127.0.0.1
local_port = 8188
remote_port = 7000
"""

with open("/tmp/frpc.toml", "w") as f:
    f.write(frpc_config)

!nohup /usr/local/bin/frpc -c /tmp/frpc.toml > /dev/null 2>&1 &
!sleep 2
!curl -s http://localhost:8188/system_stats | head -c 200
```

### Установка ComfyUI (если не установлен)

```python
# Cell 0: Check and install
import os
if not os.path.exists("/content/ComfyUI"):
    !git clone https://github.com/comfyanonymous/ComfyUI.git
    %cd /content/ComfyUI
    !pip install -r requirements.txt

# Start ComfyUI
!cd /content/ComfyUI && python main.py --listen 0.0.0.0 --port 8188 > /dev/null 2>&1 &
```

### Проверка connectivity

```python
from app.comfy.client import ComfyClient
client = ComfyClient(base_url=f"http://{VPS_IP}:7000", timeout=60)
stats = client.get_system_stats()
print(f"GPU: {stats['devices'][0]['name']}")
print(f"ComfyUI: {stats['system']['comfyui_version']}")
```

---

## E. WEBSOCKET COMPATIBILITY

### Текущая реализация (websocket.py:28-32)

```python
def __init__(self, base_url: str, client_id: str) -> None:
    scheme = "wss" if base_url.startswith("https") else "ws"
    host = base_url.split("//", 1)[-1].rstrip("/")
    self.ws_url = f"{scheme}://{host}/ws?client_id={client_id}"
```

### FRP + WebSocket

**Критический момент:** WebSocket через FRP TCP требует:
1. FRP должен проксировать WebSocket upgrade (Connection: upgrade)
2. FRP поддерживает это из коробки (TCP proxy перенаправляет все данные)
3. Коммутатор WebSocket работает через любой TCP туннель

**Проверка:** FRP TCP mode transparently forwards all bytes — WebSocket handshake проходит как обычный TCP stream.

**Результат:** `ws://VPS_IP:7000/ws?client_id=xxx` будет работать.

### Потенциальные проблемы

| Проблема | Решение |
|----------|---------|
| FRP timeout на длинных WS | Увеличить `dashboard_timeout` в frps.toml |
| WebSocket disconnect при перегрузке | Увеличить `ws_timeout` в ComfyClient (уже есть fallback на /history) |
| Large /object_info (~1.6MB) | Уже исправлено в M25: chunked reading |

---

## F. SECURITY CONSIDERATIONS

### Риски

| Риск | Уровень | Митигация |
|------|---------|-----------|
| Открытый порт 7000 | HIGH | Ограничить IP whitelist в Security Group |
| FRP token brute-force | MEDIUM | Сложный токен, limit conn в frps |
| ComfyUI без auth | HIGH | FRP + IP whitelist, комментировать доступ |
| Передача файлов через upload | LOW | Размер ограничен MAX_UPLOAD_BYTES (200MB) |

### Рекомендации

1. **IP Whitelist:** добавить в Security Group только IP агента
2. **FRP Token:** использовать сильный токен (32+ символов)
3. **HTTPS:** если нужен HTTPS — добавить nginx reverse proxy с SSL
4. **Monitor:** отслеживать нагрузку на VPS (free tier limits)

### Без изменений кода

Безопасность — полностью инфраструктурный concern. Agent не знает о FRP.

---

## G. M25 IMPACT

### Код: 0 изменений

| Компонент | Требуется изменение? | Причина |
|-----------|---------------------|---------|
| `ComfyClient` | ❌ Нет | base_url — уже параметр |
| `ComfyUIWebSocket` | ❌ Нет | ws/wss auto-detect по scheme |
| `ComfyUIProvider` | ❌ Нет | абстракция уже существует |
| `ConversationAgent` | ❌ Нет | использует provider напрямую |
| `ExecutionChain` | ❌ Нет | middleware, не знает о backend |
| `WorkflowEngine` | ❌ Нет | media-agnostic, один path |
| `AssetStore` | ❌ Нет | локальный, после upload |
| `M25 multi-asset` | ❌ Нет | работает через тот же path |
| `ChainExperience` | ❌ Нет | запись после completion |
| `verify_sequence` | ❌ Нет | проверяет локальные IDs |

### Environment change только

```diff
- COMFY_REMOTE_URL=https://xxx.trycloudflare.com  # unstable
+ COMFY_REMOTE_URL=http://VPS_IP:7000             # stable
```

### Единственное ограничение

**ComfyUI должен слушать на 0.0.0.0:8188** (уже сделано в M5 HANDOFF).

---

## H. EXACT MINIMAL IMPLEMENTATION PLAN

### ШАГ 1: Oracle Cloud VPS (однократно)

```bash
# 1. Создать VM (Oracle Cloud Free Tier)
#    — VM.Standard.A1.Flex, Ubuntu 22.04
#    — привязать Persistent External IP

# 2. Настроить Security List
#    — inbound: TCP 7000, 7500 from 0.0.0.0/0

# 3. Установить frps
wget https://github.com/fatedier/frp/releases/download/v0.60.0/frp_0.60.0_linux_arm64.tar.gz
tar zxvf frp_0.60.0_linux_arm64.tar.gz
cd frp_0.60.0_linux_arm64

# 4. Создать frps.toml
cat > frps.toml << 'EOF'
bindPort = 7000
token = "YOUR_STRONG_SECRET_TOKEN"
webServer.addr = "0.0.0.0"
webServer.port = 7500
EOF

# 5. Запустить
./frps -c frps.toml &

# 6. Запомнить: VPS_PUBLIC_IP, TOKEN
```

### ШАГ 2: Colab Notebook (каждый запуск)

```python
# Cell 1: Setup FRP client
VPS_IP = "YOUR_VPS_PUBLIC_IP"
TOKEN = "YOUR_STRONG_SECRET_TOKEN"
COMFY_REMOTE_URL = f"http://{VPS_IP}:7000"

!wget -q https://github.com/fatedier/frp/releases/download/v0.60.0/frp_0.60.0_linux_amd64.tar.gz
!tar zxvf frp_0.60.0_linux_amd64.tar.gz
!cp frp_0.60.0_linux_amd64/frpc /usr/local/bin/

import os
frpc_cfg = f"""
server_addr = "{VPS_IP}"
server_port = 7000
token = "{TOKEN}"

[comfyui]
type = tcp
local_ip = 127.0.0.1
local_port = 8188
remote_port = 7000
"""
with open("/tmp/frpc.toml", "w") as f:
    f.write(frpc_cfg)

!nohup /usr/local/bin/frpc -c /tmp/frpc.toml > /dev/null 2>&1 &
!sleep 2

# Cell 2: Check connectivity
from app.comfy.client import ComfyClient
client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=60)
stats = client.get_system_stats()
print(f"OK: {stats['system']['comfyui_version']}, GPU: {stats['devices'][0]['name']}")
```

### ШАГ 3: Запуск M25 E2E

```python
import os
os.environ["COMFY_REMOTE_URL"] = "http://YOUR_VPS_IP:7000"

# Then run:
# python tests/_m25_e2e_runner.py
```

---

## I. RISKS / GAPS

### Известные риски

| Риск | Вероятность | Влияние | Mitigation |
|------|-------------|---------|------------|
| VPS бесплатный лимит | LOW | МEDIUM | Oracle Free Tier щедрый (10GB RAM, 4 OCPU) |
| FRP disconnect | LOW | MEDIUM | Auto-restart frpc в Colab |
| ComfyUI OOM | MEDIUM | HIGH | Tesla T4 15GB — достаточно для SD 1.5 |
| WebSocket timeout | LOW | MEDIUM | Уже есть /history fallback |
| IP VPS меняется | LOW | HIGH | Persistent IP при создании VM |

### GAP REPORT

```
GAP: None (architecturally)

Все необходимые компоненты уже существуют:
  ✅ ComfyClient(base_url) — параметризован
  ✅ WebSocket ws/wss auto-detect
  ✅ Provider/Backend boundary — remote first-class
  ✅ M20 Gateway — optional, не требуется для direct path

Минимальное изменение:
  Только env var COMFY_REMOTE_URL
  + настройка инфраструктуры (VPS + frps + frpc)
  БЕЗ изменений в коде Agent
```

### Когда потребуется код

Если появятся следующие требования:
1. Multi-backend failover (Gateway routing)
2. Health-check based selection
3. Token-based auth for FRP
4. Auto-reconnect logic

**НО для текущей задачи — НЕ требуется.**

---

## РЕЗЮМЕ

```
FRP INTEGRATION: NO CODE CHANGE REQUIRED

Architecture:
  Agent → ComfyClient → FRP Tunnel → ComfyUI
           (unchanged)    (infra only)  (unchanged)

Required:
  1. Oracle Cloud VPS (free tier)
  2. FRP server (frps) on VPS
  3. FRP client (frpc) on Colab
  4. COMFY_REMOTE_URL=http://VPS_IP:7000
  5. ComfyUI --listen 0.0.0.0 --port 8188

M25 E2E will work without any code modification.
```

---

**СТОП.** Жду команду на реализацию инфраструктуры или перехода к следующему этапу.
