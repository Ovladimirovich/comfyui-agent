# ComfyUI-Agent-Panel

Панель управления агентом для ComfyUI.
Установка: `custom_nodes/comfyui-agent-panel`

---

## AgentPanel
- **Category:** Agent/Panel
- **Purpose:** Веб-панель для управления агентом
- **Module:** custom_nodes.comfyui-agent-panel
- **Related:** Agent tasks

**Inputs:**
- `task` (STRING): Задача для выполнения
- `model` (STRING, optional): Модель для использования

**Outputs:**
- `result` (STRING): Результат выполнения
- `status` (STRING): Статус (pending/completed/failed)

**Configuration:**
- Panel доступен по адресу: http://127.0.0.1:8188/agent-panel
- Требует настройки API ключей
