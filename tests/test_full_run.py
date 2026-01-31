import cv2
import os
import re
import pandas as pd
from ultralytics import YOLO
import easyocr
import numpy as np
import time  # <--- Добавили для замера времени

# ========================================================
# 1. КЛАССЫ ЛОГИКИ (Matcher и TimeLogic - без изменений)
# ========================================================

class ProtocolMatcher:
    def __init__(self, file_path):
        self.db = {}
        if not os.path.exists(file_path):
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Файл {file_path} не найден!")
            return

        df = None
        encodings = ['utf-8', 'cp1251', 'utf-8-sig']
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc, sep=None, engine='python')
                break
            except Exception:
                continue
        
        if df is not None:
            df.columns = [c.lower().strip() for c in df.columns]
            for _, row in df.iterrows():
                num_val = str(row['number']).split('.')[0].strip()
                name_val = str(row['name']).strip()
                self.db[num_val] = name_val
            print(f"✅ Протокол загружен: {len(self.db)} участников.")

    def find_participant(self, raw_ocr_text):
        if not raw_ocr_text: return None, None
        text = str(raw_ocr_text).upper()
        text = text.replace('Z', '2').replace('O', '0').replace('I', '1').replace('L', '1')
        text = re.sub(r'\D', '', text).lstrip('0')
        if text == "" or len(text) > 4: return None, None
        name = self.db.get(text)
        return (text, name) if name else (None, None)

class TimeLogicManager:
    def __init__(self, conf_limit=3):
        self.conf_limit = conf_limit
        self.confirmed_athletes = set() 
        self.candidates = {} 
        self.results = []     

    def process_frame(self, matched_list, current_time):
        for num, name in matched_list:
            if num in self.confirmed_athletes:
                continue 
            if num not in self.candidates:
                self.candidates[num] = [1, current_time, name]
            else:
                self.candidates[num][0] += 1
                if self.candidates[num][0] >= self.conf_limit:
                    first_seen = self.candidates[num][1] 
                    self.results.append({"time": first_seen, "num": num, "name": name})
                    self.confirmed_athletes.add(num)
                    print(f"✨ ПОДТВЕРЖДЕНО: {first_seen} {num} {name}")
                    del self.candidates[num]

def format_time(ms):
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    return f"{minutes:02d}:{seconds:02d}"

# ========================================================
# 2. ОСНОВНОЙ ПАЙПЛАЙН С ЗАМЕРОМ ВРЕМЕНИ
# ========================================================

def run_full_test():
    # Начало замера общего времени выполнения
    overall_start_time = time.time() 

    VIDEO_PATH = "../input/videos/test_video_long.mp4"
    CSV_PATH = "../input/protocols/protocol.csv"
    DEBUG_DIR = "../outputs/detected/debug_frames/"
    
    if not os.path.exists(DEBUG_DIR):
        os.makedirs(DEBUG_DIR)

    print("⏳ Загрузка моделей...")
    model_yolo = YOLO('yolov8n.pt') 
    reader = easyocr.Reader(['en'], gpu=False) # Твой Intel i7 работает на CPU
    
    matcher = ProtocolMatcher(CSV_PATH)
    brain = TimeLogicManager(conf_limit=3)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"❌ Ошибка открытия видео: {VIDEO_PATH}")
        return

    interval_ms = 3000 
    current_ms = 0
    frame_count = 0 # Счетчик обработанных кадров

    print(f"🚀 Старт обработки. Видео: {VIDEO_PATH}")
    print("-" * 50)

    while cap.isOpened():
        cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        timestamp = format_time(current_ms)
        matched_on_frame = []

        # Детекция YOLO
        results = model_yolo(frame, verbose=False)[0]
        
        for i, box in enumerate(results.boxes.xyxy):
            cls = int(results.boxes.cls[i])
            if cls == 0: # Person
                x1, y1, x2, y2 = map(int, box)
                crop_y2 = y1 + (y2 - y1) // 2 
                crop_back = frame[y1:crop_y2, x1:x2]

                if crop_back.size > 0:
                    # OCR
                    ocr_results = reader.readtext(crop_back)
                    for (_, text, conf) in ocr_results:
                        num, name = matcher.find_participant(text)
                        if num:
                            matched_on_frame.append((num, name))

        brain.process_frame(matched_on_frame, timestamp)
        current_ms += interval_ms

    cap.release()

    # Конец замера времени
    overall_end_time = time.time()
    total_duration = overall_end_time - overall_start_time

    # ========================================================
    # 3. ТЕХНИЧЕСКИЙ ОТЧЕТ ДЛЯ ДИПЛОМА
    # ========================================================
    print("\n" + "="*40)
    print("📊 ТЕХНИЧЕСКИЙ ОТЧЕТ ПО ПРОИЗВОДИТЕЛЬНОСТИ:")
    print("="*40)
    print(f"Железо: Intel(R) Core(TM) i7-1165G7 (CPU mode)")
    print(f"Общее время выполнения: {total_duration:.2f} сек.")
    print(f"Всего обработано кадров: {frame_count}")
    if frame_count > 0:
        print(f"Средняя скорость обработки 1 кадра: {total_duration / frame_count:.2f} сек.")
    
  # Считаем "коэффициент реальности"
    # (Если видео длилось 60 сек, а обработалось за 30 - скорость 2.00x)
    video_duration_sec = current_ms / 1000
    if total_duration > 0:
        multiplier = video_duration_sec / total_duration
        # Заменили :.2x на :.2f
        print(f"Скорость относительно видео: {multiplier:.2f}x (от реального времени)")
    print("="*40)

    print("\n" + "="*40)
    print("ИТОГОВЫЙ ОТЧЕТ ПО УЧАСТНИКАМ:")
    print("="*40)
    if brain.results:
        for res in brain.results:
            print(f"{res['time']} {res['num']} {res['name']}")
    else:
        print("Спортсмены не подтверждены.")

if __name__ == "__main__":
    run_full_test()