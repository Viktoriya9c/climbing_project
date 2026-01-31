import os

print("🔍 ПРОВЕРКА ПУТЕЙ В НОВОЙ СТРУКТУРЕ")
print("=" * 50)

paths_to_check = [
    "../input/images/person_full.jpg",
    "../input/images/number_close.jpg", 
    "../input/images/first_frame.jpg",
    "../input/videos/test_video.mp4",
    "../outputs/detected/",
    "../outputs/cropped/",
    "../outputs/timestamps/",
    "../models/yolov8n.pt",
    "../temp/frames/",
    "../temp/crops/"
]

all_ok = True

for path in paths_to_check:
    exists = os.path.exists(path)
    status = "✅" if exists else "❌"
    print(f"{status} {path}")
    
    if not exists:
        # Проверяем, может это папка, которую нужно создать
        if path.endswith('/') or path.endswith('\\'):
            try:
                os.makedirs(path, exist_ok=True)
                print(f"   📁 Создана папка: {path}")
            except:
                pass
        all_ok = False

print("\n" + "=" * 50)
if all_ok:
    print("✅ ВСЕ ПУТИ СУЩЕСТВУЮТ")
else:
    print("⚠️  Некоторые пути отсутствуют (но некоторые папки созданы автоматически)")

# Дополнительная информация
print(f"\n📁 Текущая рабочая папка: {os.getcwd()}")
print(f"📁 Папка проекта: {os.path.dirname(os.getcwd())}")