import os

def format_time(ms):
    """
    Преобразует миллисекунды в текстовый формат (HH:MM:SS или MM:SS).
    """
    if ms < 0:
        return "00:00"

    # Переводим в целые секунды
    total_seconds = int(ms // 1000)
    
    # divmod(a, b) возвращает сразу два числа: (a // b, a % b)
    # Считаем часы, минуты и секунды
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Если видео длится больше часа, добавляем часы в строку
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # В обычном случае возвращаем привычные MM:SS
    return f"{minutes:02d}:{seconds:02d}"

def ensure_dir(file_path):
    """
    Создает дерево папок для указанного пути, если оно еще не существует.
    """
    if not file_path:
        return

    directory = os.path.dirname(file_path)
    
    if directory:
        # exist_ok=True заменяет проверку "if не существует". 
        # Если папка уже есть, Python просто промолчит и не выдаст ошибку.
        os.makedirs(directory, exist_ok=True)