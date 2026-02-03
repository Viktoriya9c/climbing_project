import cv2
import os
from ultralytics import YOLO
import easyocr

class ClimbingDetector:
    """Класс для компьютерного зрения: детекция людей и распознавание номеров."""
    
    def __init__(self, model_name='yolov8n.pt'):
        print("⏳ Инициализация моделей (YOLOv8, EasyOCR)...")
        self.model_yolo = YOLO(model_name)
        # gpu=False обеспечивает стабильную работу на CPU (Intel i7)
        self.reader = easyocr.Reader(['en'], gpu=False)

    def detect_and_ocr(self, frame, matcher, debug_path=None, timestamp="00-00"):
        """
        Ищет людей, вырезает область номера и распознает текст.
        debug_path: путь для сохранения кропов (если None - не сохраняем).
        """
        results = self.model_yolo(frame, verbose=False)[0]
        matched_on_frame = []

        for i, box in enumerate(results.boxes.xyxy):
            cls = int(results.boxes.cls[i])
            if cls == 0: # Класс 'person' в YOLO
                x1, y1, x2, y2 = map(int, box)
                
                # Кроп спины: берем верхнюю половину прямоугольника человека
                crop_y2 = y1 + (y2 - y1) // 2 
                crop_back = frame[y1:crop_y2, x1:x2]

                if crop_back.size > 0:
                    # Распознавание текста
                    ocr_results = self.reader.readtext(crop_back)
                    for (_, text, conf) in ocr_results:
                        num, name = matcher.find_participant(text)
                        if num:
                            matched_on_frame.append((num, name))
                            
                            # Если включен режим отладки — сохраняем кроп на диск
                            if debug_path:
                                filename = f"time_{timestamp}_num_{num}.jpg"
                                cv2.imwrite(os.path.join(debug_path, filename), crop_back)
        
        return matched_on_frame