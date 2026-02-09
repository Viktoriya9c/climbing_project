import cv2
import os
from ultralytics import YOLO
import easyocr

class ClimbingDetector:
    """Класс для компьютерного зрения: детекция людей и распознавание номеров."""
    
    def __init__(self, model_filename='yolov8n.pt'):
        # 1. Вычисляем путь к папке models относительно этого файла (src/detector.py)
        # __file__ - это путь к текущему файлу
        # os.path.abspath - делает его полным (от буквы диска)
        # os.path.dirname - отрезает имя файла, оставляя путь к папке
        current_dir = os.path.dirname(os.path.abspath(__file__)) # папка src
        project_root = os.path.dirname(current_dir) # корень проекта
        
        model_path = os.path.join(project_root, 'models', model_filename)
        
        # 2. Загружаем модель (verbose=False в YOLO убирает лишний текст в консоли)
        self.model_yolo = YOLO(model_path)
        
        # 3. Инициализируем EasyOCR (оставляем en, так как номера обычно цифры)
        # gpu=False обеспечивает стабильную работу на CPU
        self.reader = easyocr.Reader(['en'], gpu=False)

    def detect_and_ocr(self, frame, matcher, debug_path=None, timestamp="00-00"):
        """
        Ищет людей, вырезает область номера и распознает текст.
        matcher: объект класса matcher.py для сопоставления с протоколом.
        debug_path: путь для сохранения кропов (если None - не сохраняем).
        """
        # verbose=False убирает отчет о детекции каждого кадра в консоль
        results = self.model_yolo(frame, verbose=False)[0]
        matched_on_frame = []

        for i, box in enumerate(results.boxes.xyxy):
            cls = int(results.boxes.cls[i])
            
            # 0 - это класс 'person' в стандартной модели YOLO
            if cls == 0: 
                x1, y1, x2, y2 = map(int, box)
                
                # Кроп верхней части спины (где обычно номер)
                # Берем от плеч до середины туловища
                crop_y2 = y1 + (y2 - y1) // 2 
                crop_back = frame[y1:crop_y2, x1:x2]

                if crop_back.size > 0:
                    # Распознавание текста (детализацию оставляем минимальной для скорости)
                    ocr_results = self.reader.readtext(crop_back)
                    
                    for (_, text, conf) in ocr_results:
                        # Пытаемся найти участника в протоколе по распознанному тексту
                        num, name = matcher.find_participant(text)
                        
                        if num:
                            matched_on_frame.append((num, name))
                            
                            # Если задан путь для отладки — сохраняем картинку кропа
                            if debug_path:
                                filename = f"time_{timestamp}_num_{num}.jpg"
                                full_debug_path = os.path.join(debug_path, filename)
                                cv2.imwrite(full_debug_path, crop_back)
        
        return matched_on_frame