import argparse
import time
import cv2
import os
from src.matcher import ProtocolMatcher
from src.logic_manager import TimeLogicManager
from src.video_utils import format_time, ensure_dir
from src.detector import ClimbingDetector

def main():
    # Настройка аргументов командной строки
    parser = argparse.ArgumentParser(description="Автоматическая разметка скалолазного видео")
    parser.add_argument("--video", required=True, help="Путь к видеофайлу")
    parser.add_argument("--protocol", required=True, help="Путь к CSV файлу протокола")
    parser.add_argument("--interval", type=int, default=3, help="Интервал обработки (сек)")
    parser.add_argument("--conf", type=int, default=3, help="Кол-во кадров для подтверждения")
    parser.add_argument("--save-debug", action="store_true", help="Сохранять кропы найденных номеров в outputs/debug_crops/")
    
    args = parser.parse_args()

    # Подготовка папок
    LOG_PATH = "logs/last_run.txt"
    RESULT_PATH = "outputs/timestamps/result.txt"
    DEBUG_DIR = "outputs/debug_crops"
    
    ensure_dir(LOG_PATH)
    ensure_dir(RESULT_PATH)
    if args.save_debug:
        ensure_dir(os.path.join(DEBUG_DIR, "init.txt"))

    # Инициализация компонентов
    overall_start_time = time.time()
    detector = ClimbingDetector()
    matcher = ProtocolMatcher(args.protocol)
    brain = TimeLogicManager(conf_limit=args.conf)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"❌ Ошибка: Не удалось открыть видео {args.video}")
        return

    interval_ms = args.interval * 1000
    current_ms = 0
    frame_count = 0

    print(f"🚀 Старт обработки. Файл: {args.video}")

    # Основной цикл обработки видео
    while cap.isOpened():
        cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        time_str = format_time(current_ms)
        
        # 1. Детекция людей и OCR номеров
        found_matches = detector.detect_and_ocr(
            frame, 
            matcher, 
            debug_path=DEBUG_DIR if args.save_debug else None,
            timestamp=time_str.replace(":", "-")
        )
        
        # 2. Логика фильтрации (подтверждение личности)
        brain.process_frame(found_matches, time_str)
        
        current_ms += interval_ms

    cap.release()
    
    # Сбор метрик производительности
    total_duration = time.time() - overall_start_time
    video_duration_sec = current_ms / 1000
    speed_multiplier = video_duration_sec / total_duration if total_duration > 0 else 0

    # Формирование финального отчета
    report_header = "="*40 + "\n📊 ТЕХНИЧЕСКИЙ ОТЧЕТ\n" + "="*40 + "\n"
    report_body = (
        f"Файл: {args.video}\n"
        f"Общее время работы: {total_duration:.2f} сек.\n"
        f"Обработано кадров: {frame_count}\n"
        f"Скорость обработки: {speed_multiplier:.2f}x\n"
    )
    
    result_header = "\n" + "="*40 + "\nИТОГОВЫЙ СПИСОК ТАЙМКОДОВ:\n" + "="*40 + "\n"
    result_body = ""
    if brain.results:
        for res in brain.results:
            result_body += f"{res['time']} | №{res['num']} {res['name']}\n"
    else:
        result_body = "Спортсмены не подтверждены.\n"

    full_output = report_header + report_body + result_header + result_body
    print(full_output)

    # Сохранение результатов в файлы
    with open(LOG_PATH, "w", encoding="utf-8") as f: f.write(full_output)
    with open(RESULT_PATH, "w", encoding="utf-8") as f: f.write(result_body)

    print(f"💾 Отчет: {LOG_PATH}")
    if args.save_debug:
        print(f"🖼 Кропы номеров сохранены в: {DEBUG_DIR}")

if __name__ == "__main__":
    main()