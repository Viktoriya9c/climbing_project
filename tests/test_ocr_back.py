import easyocr
import cv2
import os
import numpy as np

print("🔍 ТЕСТ: Поиск номера на спине (полный рост)")
print("=" * 50)

# 1. Настройки (пути исправлены)
INPUT_IMAGE = "../input/images/person_full.jpg"  # фото человека со спины
OUTPUT_IMAGE = "../outputs/detected/back_recognized.jpg"
BACK_REGION_PATH = "../outputs/detected/back_region.jpg"  # исправлено!

# 2. Проверяем файл
if not os.path.exists(INPUT_IMAGE):
    print(f"❌ Файл {INPUT_IMAGE} не найден!")
    print(f"Текущая папка: {os.getcwd()}")
    exit()

print(f"✅ Файл найден: {INPUT_IMAGE}")

# 3. Загружаем изображение
image = cv2.imread(INPUT_IMAGE)
if image is None:
    print("❌ Не удалось загрузить изображение")
    exit()

height, width = image.shape[:2]
print(f"📏 Размер: {width}x{height} пикселей")

# 4. Создаём копию для рисования
output_image = image.copy()

# 5. ВЫРЕЗАЕМ ОБЛАСТЬ СПИНЫ
print("\n📍 Вырезаю область спины...")

# Координаты области поиска
start_y = height // 4      # начинаем с 25% высоты
end_y = height // 2        # до 50% высоты (лопатки)
start_x = width // 4       # от 25% ширины
end_x = 3 * width // 4     # до 75% ширины

back_region = image[start_y:end_y, start_x:end_x]

# Сохраняем вырезку в outputs/detected (исправлено!)
cv2.imwrite(BACK_REGION_PATH, back_region)
print(f"✅ Вырезка сохранена: {BACK_REGION_PATH}")
print(f"   Координаты: Y[{start_y}:{end_y}], X[{start_x}:{end_x}]")

# 6. Рисуем прямоугольник поиска на исходном фото
cv2.rectangle(output_image, 
              (start_x, start_y), 
              (end_x, end_y), 
              (0, 255, 255),  # жёлтый прямоугольник
              thickness=2)

# 7. Инициализируем EasyOCR
print("🔄 Загружаю EasyOCR...")
try:
    reader = easyocr.Reader(['en'])
except Exception as e:
    print(f"❌ Ошибка EasyOCR: {e}")
    exit()

print("\n🔍 Вариант 1: Ищем номер НА ВЫРЕЗКЕ (спина)")
print("-" * 40)

# Распознаём на вырезке (исправлен путь!)
results = reader.readtext(BACK_REGION_PATH, detail=1)

all_digits = []

if results:
    print(f"✅ На вырезке найдено {len(results)} текстовых фрагментов")
    
    for i, (bbox, text, confidence) in enumerate(results):
        # Преобразуем координаты вырезки в координаты исходного изображения
        adjusted_bbox = []
        for point in bbox:
            adj_x = int(point[0] + start_x)
            adj_y = int(point[1] + start_y)
            adjusted_bbox.append([adj_x, adj_y])
        
        # Рисуем bounding box (зелёная рамка для найденных на спине)
        pts = np.array(adjusted_bbox, dtype=np.int32)
        cv2.polylines(output_image, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        
        # Добавляем текст
        x_min = int(min([p[0] for p in adjusted_bbox]))
        y_min = int(min([p[1] for p in adjusted_bbox]))
        
        # Подложка
        cv2.rectangle(output_image, 
                     (x_min, y_min - 30), 
                     (x_min + 120, y_min), 
                     (0, 255, 0), 
                     -1)
        
        # Текст
        cv2.putText(output_image, 
                   f"{text} ({confidence:.0%})", 
                   (x_min + 5, y_min - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, 
                   (0, 0, 0), 
                   2)
        
        # Извлекаем цифры
        digits = ''.join([c for c in text if c.isdigit()])
        if digits:
            all_digits.append(digits)
            print(f"   Фрагмент {i+1}: '{text}' → цифры: {digits} (уверенность: {confidence:.1%})")
        else:
            print(f"   Фрагмент {i+1}: '{text}' (нет цифр)")
    
else:
    print("❌ На вырезке текст не обнаружен")

# 8. Дополнительно: ищем на всём изображении
print("\n🔍 Вариант 2: Ищем номер на ВСЁМ изображении")
print("-" * 40)

results_full = reader.readtext(INPUT_IMAGE, detail=1)

if results_full and not all_digits:  # если на вырезке не нашли
    print(f"✅ На всём фото найдено {len(results_full)} фрагментов")
    
    for i, (bbox, text, confidence) in enumerate(results_full):
        # Рисуем синие рамки для всех найденных текстов
        pts = np.array(bbox, dtype=np.int32)
        cv2.polylines(output_image, [pts], isClosed=True, color=(255, 0, 0), thickness=1)
        
        digits = ''.join([c for c in text if c.isdigit()])
        if digits:
            print(f"   Фрагмент {i+1}: '{text}' → цифры: {digits}")
            all_digits.append(digits)

# 9. Итоговый результат
print("\n" + "=" * 50)
print("📊 ИТОГИ ПОИСКА НОМЕРА НА СПИНЕ:")

if all_digits:
    final_number = ''.join(all_digits[:3])  # берём первые 3 найденные цифры
    print(f"✅ НОМЕР УЧАСТНИКА: {final_number}")
    
    # Добавляем номер в угол изображения
    cv2.putText(output_image,
               f"BIB: {final_number}",
               (20, 40),
               cv2.FONT_HERSHEY_SIMPLEX,
               1.2,
               (0, 255, 255),  # жёлтый
               3)
else:
    print("❌ Цифры не найдены")
    cv2.putText(output_image,
               "No number detected",
               (20, 40),
               cv2.FONT_HERSHEY_SIMPLEX,
               1.2,
               (0, 0, 255),
               3)

# 10. Сохраняем результат (путь уже правильный)
cv2.imwrite(OUTPUT_IMAGE, output_image)
print(f"\n💾 Результат сохранён: {OUTPUT_IMAGE}")

# 11. Что на изображении:
print("\n🎨 Легенда на изображении:")
print("   █ Жёлтый прямоугольник - область поиска (спина)")
print("   █ Зелёные рамки - текст найден на вырезке")
print("   █ Синие рамки - текст найден на всём фото")
print("   █ Жёлтый текст - итоговый номер участника")

print("\n✅ Тест завершён!")