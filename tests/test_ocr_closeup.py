import easyocr
import cv2
import os
import numpy as np

print("🔍 ТЕСТ: Распознавание номера (крупный план)")
print("=" * 50)

# 1. Настройки (пути уже правильные!)
INPUT_IMAGE = "../input/images/number_close.jpg"  # твоё фото с номером
OUTPUT_IMAGE = "../outputs/detected/number_recognized.jpg"

# 2. Проверяем файл
if not os.path.exists(INPUT_IMAGE):
    print(f"❌ Файл {INPUT_IMAGE} не найден!")
    print(f"Текущая папка: {os.getcwd()}")
    print("Проверь папку input/images/")
    exit()

print(f"✅ Файл найден: {INPUT_IMAGE}")

# 3. Загружаем изображение
image = cv2.imread(INPUT_IMAGE)
if image is None:
    print("❌ Не удалось загрузить изображение")
    exit()

height, width = image.shape[:2]
print(f"📏 Размер: {width}x{height} пикселей")

# 4. Инициализируем EasyOCR
print("🔄 Загружаю EasyOCR... (первый запуск может занять время)")
try:
    reader = easyocr.Reader(['en'])  # только английский (цифры)
    print("✅ EasyOCR готов к работе")
except Exception as e:
    print(f"❌ Ошибка загрузки EasyOCR: {e}")
    exit()

# 5. Распознаём текст
print("🔠 Распознаю текст...")
results = reader.readtext(INPUT_IMAGE, detail=1)  # detail=1 даёт координаты

# Создаём копию изображения для рисования
output_image = image.copy()

if results:
    print(f"✅ Найдено {len(results)} текстовых фрагмента(ов)")
    
    all_numbers = []
    
    for i, (bbox, text, confidence) in enumerate(results):
        # bbox содержит 4 точки [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        
        # 1. Рисуем bounding box (зелёная рамка)
        pts = np.array(bbox, dtype=np.int32)
        cv2.polylines(output_image, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        
        # 2. Рисуем текст над рамкой
        x_min = int(min([p[0] for p in bbox]))
        y_min = int(min([p[1] for p in bbox]))
        
        # Подложка для текста
        cv2.rectangle(output_image, 
                     (x_min, y_min - 30), 
                     (x_min + 100, y_min), 
                     (0, 255, 0), 
                     -1)
        
        # Сам текст
        cv2.putText(output_image, 
                   f"{text} ({confidence:.0%})", 
                   (x_min + 5, y_min - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, 
                   (0, 0, 0), 
                   2)
        
        # Собираем цифры
        digits = ''.join([c for c in text if c.isdigit()])
        if digits:
            all_numbers.append(digits)
        
        print(f"   Фрагмент {i+1}: '{text}' (уверенность: {confidence:.1%})")
    
    # 6. Выводим итоговый номер
    if all_numbers:
        final_number = ''.join(all_numbers)
        print(f"\n📟 ИТОГОВЫЙ НОМЕР: {final_number}")
        
        # Добавляем итоговый номер в угол изображения
        cv2.putText(output_image,
                   f"Number: {final_number}",
                   (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX,
                   1.2,
                   (255, 0, 0),
                   3)
    else:
        print("⚠️  Цифры не найдены в распознанном тексте")
        cv2.putText(output_image,
                   "No digits found",
                   (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX,
                   1.2,
                   (0, 0, 255),
                   3)
        
else:
    print("❌ Текст не обнаружен")
    cv2.putText(output_image,
               "No text detected",
               (20, 40),
               cv2.FONT_HERSHEY_SIMPLEX,
               1.2,
               (0, 0, 255),
               3)

# 7. Сохраняем результат (путь уже правильный)
cv2.imwrite(OUTPUT_IMAGE, output_image)
print(f"\n💾 Результат сохранён: {OUTPUT_IMAGE}")

# 8. Проверяем сохранение
if os.path.exists(OUTPUT_IMAGE):
    input_size = os.path.getsize(INPUT_IMAGE) // 1024
    output_size = os.path.getsize(OUTPUT_IMAGE) // 1024
    print(f"📁 Размеры: исходный - {input_size} КБ, результат - {output_size} КБ")
else:
    print("⚠️  Файл результата не создался!")

print("✅ Тест завершён!")