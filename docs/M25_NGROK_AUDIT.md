# ngrok Audit Report

**Статус:** BLOCKED (IP restriction)
**Дата:** 2026-09-04

---

## A. Текущая ситуация

### ngrok настроен ✅
- **Binary:** `C:\adpanel\ngrok.exe` v3.39.5
- **Auth token:** configured
- **Config:** valid

### Ошибка подключения ❌
```
authentication failed: We do not allow agents to connect to ngrok 
from your IP address (95.72.82.232). ERR_NGROK_9040
```

**Причина:** ngrok free tier restricts connecting IPs.
Ссылка: https://ngrok.com/docs/errors/err_ngrok_9040

---

## B. Local ComfyUI

```
http://127.0.0.1:8188 → Connection Refused
```
Локальный ComfyUI не запущен.

---

## C. Colab ComfyUI (предыдущий URL)

```
https://importance-kills-attempt-configurations.trycloudflare.com
→ HTTP 530 (tunnel expired)
```

---

## D. Варианты решения

### Вариант 1: Новый Cloudflare Tunnel (РЕКОМЕНДОВАНО)

**Почему:** Уже работает, бесплатный, стабильнее ngrok free tier

```python
# В Colab:
!pip install cloudflared
!cloudflared tunnel --url http://localhost:8188
# Копировать https://xxxx.trycloudflare.com
```

**Плюсы:**
- Не блокирует IP
- Бесплатно
- Работает из Colab

**Минусы:**
- URL меняется при рестарте туннеля

### Вариант 2: ngrok Pro ($6/мес)

**Требуется:** Upgrade ngrok account to Pro

**Плюсы:**
- Fixed domain option
- No IP restrictions

**Минусы:**
- Платно

### Вариант 3: Oracle Cloud VPS + FRP (из审计报告)

**Требуется:**
- Создать VPS на Oracle Cloud (free tier)
- Установить frps
- Настроить frpc в Colab

**Плюсы:**
- Stable endpoint
- Permanent URL

**Минусы:**
- Требуется инфраструктура
- Время настройки ~15 минут

---

## E. Рекомендация

**НЕ Менять код.** Существующий путь `ComfyClient(base_url=...)` работает с любым HTTP endpoint.

**Действия:**
1. Перезапустить Cloudflare Tunnel в Colab
2. Получить новый URL
3. Запустить M25 E2E с новым URL
4. Если нужен permanent URL — настроить Oracle VPS + FRP

---

## F. GAP REPORT

```
GAP: ngrok blocked by IP restriction (ERR_NGROK_9040)

Cause: ngrok free tier limits connecting IPs
Solution: Use Cloudflare Tunnel (works) or Oracle VPS + FRP (permanent)

No code changes required for either solution.
```

---

## Готово к E2E

Как только появится рабочий URL — M25 E2E готов к запуску без изменений кода:

```powershell
$env:COMFY_REMOTE_URL = "https://new-url.trycloudflare.com"
python tests/_m25_e2e_runner.py
```
