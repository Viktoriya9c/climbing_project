from ultralytics import YOLO
import cv2
import os

print("1. Загружаю модель YOLO...")
# Указываем путь к модели в папке models
model_path = "../models/yolov8n.pt"
model = YOLO(model_path)

print("2. Загружаю изображение...")
# Новый путь к изображению
image_path = "../input/images/first_frame.jpg"
image = cv2.imread(image_path)

if image is None:
    print(f"Ошибка: не могу загрузить {image_path}")
    print("Проверь, что файл существует")
    # Покажем текущую директорию для отладки
    print(f"Текущая папка: {os.getcwd()}")
else:
    print(f"✅ Изображение загружено: {image_path}")
    print(f"   Размер: {image.shape[1]}x{image.shape[0]}")
    
    print("3. Детектирую объекты...")
    results = model(image)
    
    print("4. Сохраняю результат...")
    # Новый путь для сохранения
    output_path = "../outputs/detected/detected_frame.jpg"
    
    for result in results:
        annotated = result.plot()
        cv2.imwrite(output_path, annotated)
    
    print(f"✅ Готово! Результат сохранён в: {output_path}")
    
    # Проверим, что файл создался
    if os.path.exists(output_path):
        size = os.path.getsize(output_path) // 1024
        print(f"   Размер файла результата: {size} КБ")
    else:
        print("⚠️  Файл результата не создался")