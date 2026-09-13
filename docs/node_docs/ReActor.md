# comfyui-reactor

Face swap и обработка лиц через ReActor.
Установка: `custom_nodes/comfyui-reactor`

---

## ReActor
- **Category:** ReActor
- **Purpose:** Основной нод для face swap (замена лица на изображении)
- **Module:** custom_nodes.comfyui-reactor
- **Related:** LoadFaceModel, RestoreFace, MaskHelper

**Inputs:**
- `enabled` (BOOLEAN, default: True): Включить/выключить
- `input_image` (IMAGE): Входное изображение
- `swap_model` (ENUM: [inswapper_128, insightface_i1, insightface_i2, ...]): Модель swap
- `facedetection` (ENUM: [retinaface_resnet50, retinaface_mobile0.25, YOLOv5l, YOLOv5n]): Детектор лиц
- `face_restore_model` (ENUM: [gfpgan_1.4, CodeFormer, RestoreFormer]): Модель восстановления
- `face_restore_visibility` (FLOAT, default: 1, min: 0.1, max: 1): Видимость восстановления
- `codeformer_weight` (FLOAT, default: 0.5, min: 0, max: 1): Вес CodeFormer
- `detect_gender_input` (ENUM: [no, female, male], default: no): Пол входного лица
- `detect_gender_source` (ENUM: [no, female, male], default: no): Пол источника
- `input_faces_index` (STRING, default: "0"): Индексы входных лиц (через запятую)
- `source_faces_index` (STRING, default: "0"): Индексы исходных лиц

**Outputs:**
- `image` (IMAGE): Изображение с заменённым лицом
- `face_model` (FACE_MODEL): Сохранённая модель лица
- `original_image` (IMAGE): Исходное изображение

**Configuration:**
- Models: загружаются автоматически при первом использовании
- Device: CPU/GPU (авто)

---

## LoadFaceModel
- **Category:** ReActor
- **Purpose:** Загрузка модели лица из файла
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `face_model` (ENUM): Название модели лица

**Outputs:**
- `FACE_MODEL` (FACE_MODEL): Модель лица
- `STRING` (STRING): Название модели

---

## RestoreFace
- **Category:** ReActor
- **Purpose:** Восстановление лиц на изображении
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image` (IMAGE): Входное изображение
- `facedetection` (ENUM: [retinaface_resnet50, retinaface_mobile0.25, YOLOv5l, YOLOv5n]): Детектор
- `model` (ENUM: [gfpgan_1.4, CodeFormer, RestoreFormer]): Модель восстановления
- `visibility` (FLOAT, default: 1): Видимость
- `codeformer_weight` (FLOAT, default: 0.5): Вес CodeFormer

**Outputs:**
- `image` (IMAGE): Восстановленное изображение

---

## RestoreFaceAdvanced
- **Category:** ReActor
- **Purpose:** Продвинутое восстановление лиц
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image` (IMAGE): Входное изображение
- `facedetection` (ENUM): Детектор
- `model` (ENUM): Модель
- `visibility` (FLOAT): Видимость
- `codeformer_weight` (FLOAT): Вес CodeFormer
- `face_selection` (ENUM: [all, filter, largest], default: all): Выбор лиц
- `sort_by` (ENUM: [area, x_position, y_position, detection_confidence], default: area): Сортировка
- `reverse_order` (BOOLEAN, default: False): Реверс порядка
- `take_start` (INT, default: 0): Начальный индекс

**Outputs:**
- `image` (IMAGE): Восстановленное изображение

---

## MaskHelper
- **Category:** ReActor
- **Purpose:** Создание масок для face swap (SAM, bbox, segm)
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image` (IMAGE): Входное изображение
- `mask_type` (ENUM: [bbox/all, segm/all, sam/all]): Тип маски
- `model` (STRING): Модель (SAM/bbox/segm)
- `bbox_x1` (INT, default: 0): Левая граница
- `bbox_y1` (INT, default: 0): Верхняя граница
- `bbox_x2` (INT, default: 1024): Правая граница
- `bbox_y2` (INT, default: 1024): Нижняя граница

**Outputs:**
- `image` (IMAGE): Исходное изображение
- `MASK` (MASK): Маска
- `masked_image` (IMAGE): masked изображение
- `mask_color` (IMAGE): Цветная маска

---

## ReActorOptions
- **Category:** ReActor
- **Purpose:** Настройки порядка лиц
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `input_faces_order` (ENUM: [left-right, right-left, top-bottom, bottom-top, small-large, large-small], default: large-small): Порядок входных лиц
- `input_faces_index` (STRING, default: "0"): Индексы
- `detect_gender_input` (ENUM: [no, female, male], default: no): Пол
- `source_faces_order` (ENUM: [left-right, right-left, top-bottom, bottom-top, small-large, large-small], default: large-small): Порядок исходных лиц
- `source_faces_index` (STRING, default: "0"): Индексы
- `detect_gender_source` (ENUM: [no, female, male], default: no): Пол
- `console_log_level` (INT, default: 1): Уровень логов

**Outputs:**
- `OPTIONS` (OPTIONS): Настройки

---

## ReActorFaceBoost
- **Category:** ReActor
- **Purpose:** Улучшение качества лиц (boost)
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `enabled` (BOOLEAN, default: True): Включить
- `boost_model` (ENUM): Модель улучшения
- `interpolation` (ENUM: [Nearest, Bilinear, Bicubic, Lanczos], default: Bicubic): Интерполяция
- `visibility` (FLOAT, default: 1): Видимость
- `codeformer_weight` (FLOAT, default: 0.5): Вес CodeFormer
- `restore_with_main_after` (BOOLEAN, default: False): Восстановление после main

**Outputs:**
- `FACE_BOOST` (FACE_BOOST): Boost модель

---

## ReActorUnload
- **Category:** ReActor
- **Purpose:** Выгрузка моделей из памяти
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `trigger` (IMAGE): Триггер (любое изображение)

**Outputs:**
- `IMAGE` (IMAGE): То же изображение (для continuation)

---

## ReActorFaceSimilarity
- **Category:** ReActor
- **Purpose:** Сравнение схожести лиц
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image1` (IMAGE): Первое изображение
- `image2` (IMAGE): Второе изображение

**Outputs:**
- `FLOAT` (FLOAT): Схожесть (0-1)
- `STRING` (STRING): Текстовое описание схожести

---

## ImageDublicator
- **Category:** ReActor
- **Purpose:** Дублирование изображений (batch)
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image` (IMAGE): Входное изображение

**Outputs:**
- `IMAGE` (IMAGE): Изображение

---

## ImageRGBA2RGB
- **Category:** ReActor
- **Purpose:** Конвертация RGBA → RGB
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `image` (IMAGE): RGBA изображение

**Outputs:**
- `IMAGE` (IMAGE): RGB изображение

---

## MakeFaceModelBatch
- **Category:** ReActor
- **Purpose:** Создание batch модели лиц
- **Module:** custom_nodes.comfyui-reactor

**Inputs:**
- `images` (IMAGE): Batch изображений с лицами

**Outputs:**
- `FACE_MODEL` (FACE_MODEL): Модель лица
