import sys
sys.path.append('..')  # чтобы импортировать из src/

import cv2
from ultralytics import YOLO
from src.sort import Sort  # будем создавать

print("🧪 Тест трекера SORT")

# 1. Загружаем изображение с несколькими людьми
image_path = "../input/images/person_full.jpg"  # пока тестируем на одном
image = cv2.imread(image_path)

if image is None:
    print("❌ Не могу загрузить изображение")
    exit()

# 2. Инициализируем YOLO
model = YOLO("../models/yolov8n.pt")

# 3. Детектируем людей
results = model(image)
detections = []

for result in results:
    for box in result.boxes:
        # Берем только класс "человек" (class_id = 0 в COCO)
        if int(box.cls[0]) == 0:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = box.conf[0].item()
            detections.append([x1, y1, x2, y2, conf])

print(f"✅ Найдено людей: {len(detections)}")

# 4. Создаём трекер (пока заглушка)
print("📦 Инициализация трекера...")
# sort_tracker = Sort()  # пока закомментировано

print("✅ Тест готов к работе с трекером")
