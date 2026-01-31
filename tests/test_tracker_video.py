import sys
sys.path.append('..')

import cv2
import numpy as np
from ultralytics import YOLO
from src.sort import Sort

print("🎬 ТЕСТ ТРЕКИНГА С НАСТРОЙКАМИ")
print("=" * 50)

video_path = "../input/videos/test_video.mp4"
cap = cv2.VideoCapture(video_path)

fps = cap.get(cv2.CAP_PROP_FPS)
frame_skip = int(fps / 2)  # 2 кадра в секунду
print(f"📹 FPS: {fps:.1f}, обрабатываем каждый {frame_skip}-й кадр")

# БОЛЕЕ СТРОГИЕ ПАРАМЕТРЫ
model = YOLO("../models/yolov8n.pt")
tracker = Sort(max_age=5, min_hits=1, iou_threshold=0.5)

print("\n🔍 Обработка...")

frame_count = 0
processed_frames = 0
id_history = {}
all_ids = set()

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    
    if frame_count % frame_skip != 0:
        continue
    
    processed_frames += 1
    time_sec = frame_count / fps
    
    # ДЕТЕКЦИЯ С ФИЛЬТРОМ УВЕРЕННОСТИ
    results = model(frame)
    detections = []
    
    for result in results:
        for box in result.boxes:
            if int(box.cls[0]) == 0:  # человек
                conf = box.conf[0].item()
                if conf > 0.5:  # ТОЛЬКО УВЕРЕННЫЕ
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append([x1, y1, x2, y2, conf])
    
    # ТРЕКИНГ
    if detections:
        dets = np.array(detections)
        tracked_objects = tracker.update(dets)
        
        frame_ids = []
        if tracked_objects.size > 0:
            for obj in tracked_objects:
                obj_id = int(obj[4])
                frame_ids.append(obj_id)
                all_ids.add(obj_id)
        
        id_history[time_sec] = frame_ids

cap.release()

# АНАЛИЗ
print(f"\n📊 РЕЗУЛЬТАТЫ:")
print(f"   Кадров: {processed_frames}, Уникальных ID: {len(all_ids)}")

if all_ids:
    print(f"   Все ID: {sorted(all_ids)}")
    
    # Считаем стабильность
    from collections import Counter
    all_id_list = []
    for ids in id_history.values():
        all_id_list.extend(ids)
    
    id_counts = Counter(all_id_list)
    print(f"\n📈 СТАБИЛЬНОСТЬ ID:")
    for id_num, count in sorted(id_counts.items()):
        percentage = (count / processed_frames) * 100
        print(f"   ID {id_num}: {count}/{processed_frames} кадров ({percentage:.0f}%)")
    
    # Критерий успеха
    stable_ids = [id for id, count in id_counts.items() if count >= processed_frames * 0.7]
    if len(stable_ids) >= 2:  # Ожидаем 2 стабильных ID (2 человека)
        print(f"\n✅ УСПЕХ! Стабильные ID: {stable_ids}")
    else:
        print(f"\n⚠️  Проблема: мало стабильных ID")

print("\n📈 ИСТОРИЯ:")
for time_sec, ids in sorted(id_history.items()):
    print(f"   {time_sec:.1f} сек: ID {ids}")

print("\n✅ Тест завершён!")