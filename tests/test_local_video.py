import cv2
import os

video_path = "../input/videos/test_video.mp4"

# Проверяем, есть ли файл
if not os.path.exists(video_path):
    print(f"❌ Файл {video_path} не найден!")
    print(f"Текущая папка: {os.getcwd()}")
    print("Положи видеофайл в папку input/videos/")
else:
    print(f"✅ Видеофайл найден: {video_path}")
    
    # Открываем видео
    cap = cv2.VideoCapture(video_path)
    
    # Получаем свойства видео
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps
    
    print(f"✅ FPS: {fps}")
    print(f"✅ Количество кадров: {frame_count}")
    print(f"✅ Длительность: {duration:.2f} секунд")
    
    # Читаем первый кадр
    ret, frame = cap.read()
    if ret:
        # Сохраняем первый кадр в outputs/detected/
        output_path = "../outputs/detected/first_frame.jpg"
        cv2.imwrite(output_path, frame)
        print(f"✅ Первый кадр сохранён как: {output_path}")
        
        # Проверяем сохранение
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) // 1024
            print(f"   Размер: {size} КБ")
    else:
        print("❌ Не удалось прочитать кадры")
    
    cap.release()
    print("✅ Видео успешно обработано")