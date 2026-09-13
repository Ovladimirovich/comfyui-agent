# websocket_image_save

WebSocket-based image saving for ComfyUI.
Установка: `custom_nodes/websocket_image_save.py`

---

## SaveImageWebsocket
- **Category:** image
- **Purpose:** Сохранение изображений через WebSocket (без метаданных)
- **Module:** custom_nodes.websocket_image_save
- **Related:** SaveImage, SaveImageAdvanced

**Inputs:**
- `images` (IMAGE): Изображения для сохранения

**Outputs:**
- (No outputs — output node)

**Configuration:**
- Формат: PNG
- Метод: WebSocket binary transfer
- Metadata: Не сохраняется
-用途: Отправка изображений фронтенду через WebSocket

**Example:**
```json
{"images": [IMAGE]}
```
