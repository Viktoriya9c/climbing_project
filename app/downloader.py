import yt_dlp
import os

def download_video(url, output_dir="temp_data", progress_callback=None, start_time=None, end_time=None):
    """
    Скачивает видео. Использует фиксированное имя файла, 
    чтобы предотвратить накопление дубликатов на диске.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Шаг 1: Фиксируем имя файла
    # Больше никакого uuid, файл всегда будет называться одинаково
    target_path = os.path.join(output_dir, "web_download.mp4")

    # Шаг 2: Если такой файл уже есть, пытаемся его удалить перед закачкой
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
        except Exception:
            # Если файл занят (например, открыт в плеере), просто идем дальше, 
            # yt-dlp попробует его перезаписать сам
            pass

    def ytdl_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            p_str = d.get('_percent_str', '0%').replace('%','').strip()
            try:
                progress_callback(float(p_str) / 100)
            except ValueError:
                pass

    ydl_opts = {
        'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
        'outtmpl': target_path, # Используем наш фиксированный путь
        'progress_hooks': [ytdl_hook],
        'noplaylist': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'nocheckcertificate': True,
        'overwrites': True, # Разрешаем библиотеке перезаписывать файлы
    }

    # Логика обрезки через FFmpeg (без изменений)
    if start_time is not None and end_time is not None:
        ydl_opts['external_downloader'] = 'ffmpeg'
        ydl_opts['external_downloader_args'] = {
            'ffmpeg_i': [
                '-ss', str(start_time), 
                '-to', str(end_time)
            ]
        }
        ydl_opts['download_sections'] = [{
            'start_time': start_time,
            'end_time': end_time,
        }]
        ydl_opts['force_keyframes_at_cuts'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Возвращаем путь к нашему фиксированному файлу
            return target_path, info.get('title', 'Video')
    except Exception as e:
        raise Exception(f"Ошибка при скачивании фрагмента: {str(e)}")