import sys
sys.path.append('..')

import cv2
import numpy as np
from ultralytics import YOLO
from src.sort import Sort

print("🧗 ТРЕКИНГ: НАСТРОЙКА")
print("=" * 40)

# ТОЛЬКО ОДНО ВИДЕО ДЛЯ ТЕСТА
video_path = "../input/videos/test_climbing1.mp4"
print(f"📹 {video_path.split('/')[-1]}")

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)

# БОЛЬШЕ КАДРОВ ДЛЯ ТРЕКИНГА
frame_skip = max(1, int(fps / 10))  # 10 кадров/сек вместо 3
print(f"   FPS: {fps:.0f}, обрабатываем каждый {frame_skip}-й кадр")

# НАСТРОЙКИ SORT
model = YOLO("../models/yolov8n.pt")
tracker = Sort(
    max_age=3,           # быстро забывать (было 10)
    min_hits=1,          # сразу начинать трекинг
    iou_threshold=0.7    # требовать много пересечения (было 0.4)
)

frame_count = 0
id_counter = {}
bbox_history = {}  # история координат для каждого ID

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    if frame_count % frame_skip != 0:
        continue
    
    # ДЕТЕКЦИЯ
    results = model(frame, classes=[0])  # только люди
    detections = []
    
    for result in results:
        for box in result.boxes:
            conf = box.conf[0].item()
            if conf > 0.5:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # ФИЛЬТР ПО РАЗМЕРУ (игнорируем слишком мелкие/крупные)
                width = x2 - x1
                height = y2 - y1
                area = width * height
                frame_area = frame.shape[0] * frame.shape[1]
                
                if 0.01 < area/frame_area < 0.5:  # от 1% до 50% кадра
                    detections.append([x1, y1, x2, y2, conf])
    
    # ТРЕКИНГ
    if detections:
        dets = np.array(detections)
        tracked = tracker.update(dets)
        
        for obj in tracked:
            x1, y1, x2, y2, obj_id = obj
            obj_id = int(obj_id)
            
            # СГЛАЖИВАНИЕ КООРДИНАТ (простое среднее)
            if obj_id not in bbox_history:
                bbox_history[obj_id] = []
            
            bbox_history[obj_id].append([x1, y1, x2, y2])
            
            # Держим только последние 5 позиций
            if len(bbox_history[obj_id]) > 5:
                bbox_history[obj_id].pop(0)
            
            id_counter[obj_id] = id_counter.get(obj_id, 0) + 1
    
    # Визуализация каждые 50 кадров
    if frame_count % (frame_skip * 50) == 0:
        print(f"   Обработано кадров: {frame_count//frame_skip}")

cap.release()

# РЕЗУЛЬТАТ
total_frames = frame_count // frame_skip
print(f"\n📊 РЕЗУЛЬТАТЫ:")
print(f"   Всего кадров: {total_frames}")

if id_counter:
    # Стабильные ID (присутствуют > 70% времени)
    stable_ids = []
    for obj_id, count in id_counter.items():
        percent = (count / total_frames) * 100
        
        # Дополнительная проверка: был ли ID в конце видео?
        if percent > 70 and obj_id in bbox_history:
            stable_ids.append(obj_id)
        
        status = "✅" if percent > 70 else "⚠️ "
        print(f"   {status} ID {obj_id}: {count}/{total_frames} ({percent:.0f}%)")
    
    print(f"\n   Стабильные ID (>70%): {stable_ids}")
    
    # Информация о позициях
    if stable_ids:
        print(f"\n   📍 ПОЗИЦИИ СТАБИЛЬНЫХ ID:")
        for obj_id in stable_ids:
            if obj_id in bbox_history and bbox_history[obj_id]:
                avg_bbox = np.mean(bbox_history[obj_id], axis=0)
                print(f"      ID {obj_id}: [{avg_bbox[0]:.0f}, {avg_bbox[1]:.0f}, "
                      f"{avg_bbox[2]:.0f}, {avg_bbox[3]:.0f}]")
else:
    print("   ❌ Люди не обнаружены")

print("\n✅ Тест завершён")