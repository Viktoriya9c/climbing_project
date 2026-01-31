import pandas as pd
import os
import re

# ========================================================
# 1. Менеджер Протокола (Второй фактор защиты: Логика)
# ========================================================
class ProtocolMatcher:
    def __init__(self, file_path):
        self.db = {}
        if not os.path.exists(file_path):
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Файл {file_path} не найден!")
            return

        # Пытаемся прочитать файл максимально гибко
        df = None
        # Список кодировок для проверки
        encodings = ['utf-8', 'cp1251', 'utf-8-sig']
        
        for enc in encodings:
            try:
                # sep=None и engine='python' заставляют pandas саму угадать , или ;
                df = pd.read_csv(file_path, encoding=enc, sep=None, engine='python')
                break # Если прочитали успешно, выходим из цикла
            except Exception:
                continue
        
        if df is None:
            print("ОШИБКА: Не удалось прочитать CSV. Проверьте формат файла.")
            return

        # Приводим названия колонок к нижнему регистру, чтобы избежать ошибок с "Number"/"number"
        df.columns = [c.lower().strip() for c in df.columns]
        
        if 'number' not in df.columns or 'name' not in df.columns:
            print(f"ОШИБКА: В CSV не найдены колонки 'number' и 'name'. Найдено: {list(df.columns)}")
            return

        for _, row in df.iterrows():
            # Очищаем данные от лишних пробелов и точек
            num_val = str(row['number']).split('.')[0].strip()
            name_val = str(row['name']).strip()
            self.db[num_val] = name_val

    def find_participant(self, raw_ocr_text):
        """Очистка OCR и поиск в базе"""
        if not raw_ocr_text: return None, None
        
        # Очистка (Z->2, O->0, № и т.д.)
        text = str(raw_ocr_text).upper()
        text = text.replace('Z', '2').replace('O', '0').replace('№', '')
        text = text.replace('I', '1').replace('L', '1').replace('|', '1')
        text = re.sub(r'\D', '', text) # Оставить только цифры
        text = text.lstrip('0')        # Убрать ведущие нули
        
        if text == "" or len(text) > 4: return None, None
        
        # Поиск в протоколе
        name = self.db.get(text)
        return (text, name) if name else (None, None)

# ========================================================
# 2. Менеджер Времени (Третий фактор: Подтверждение)
# ========================================================
class TimeLogicManager:
    def __init__(self, conf_limit=3):
        self.conf_limit = conf_limit
        self.confirmed_athletes = set() 
        self.candidates = {}  # {номер: [счетчик, время_первого_появления, ФИО]}
        self.results = []     

    def process_frame(self, matched_list, current_time):
        for num, name in matched_list:
            if num in self.confirmed_athletes:
                continue 
            
            if num not in self.candidates:
                self.candidates[num] = [1, current_time, name]
                print(f"[{current_time}] Заметили №{num} ({name}). Ждем подтверждения...")
            else:
                self.candidates[num][0] += 1
                count = self.candidates[num][0]
                
                if count >= self.conf_limit:
                    first_seen = self.candidates[num][1] 
                    self.results.append({"time": first_seen, "num": num, "name": name})
                    self.confirmed_athletes.add(num)
                    print(f"!!! ПОДТВЕРЖДЕНО [{current_time}]: {name} (№{num}) начал в {first_seen}")
                    del self.candidates[num]

# ========================================================
# 3. ЗАПУСК ИМИТАЦИИ (ПЕСОЧНИЦА)
# ========================================================
if __name__ == "__main__":
    csv_path = os.path.join("input", "protocols", "protocol_simple.csv")
    
    matcher = ProtocolMatcher(csv_path)
    brain = TimeLogicManager(conf_limit=3)

    # Имитируем поток данных из видео
    video_stream = [
        ("00:03", ["4Z"]),
        ("00:06", ["4Z", "12"]),
        ("00:09", ["42", "99"]),
        ("00:12", ["12", "012"]),
        ("00:15", ["12"]),
        ("00:18", ["12", "7"]),
        ("00:21", ["7"]),
        ("00:24", ["7"]),
    ]

    print(f"Запуск симуляции. Протокол содержит {len(matcher.db)} участников.\n")
    
    for time, ocr_data in video_stream:
        matched_on_frame = []
        for raw in ocr_data:
            num, name = matcher.find_participant(raw)
            if num:
                matched_on_frame.append((num, name))
        
        brain.process_frame(matched_on_frame, time)

    print("\n" + "="*40)
    print("ИТОГОВАЯ ТАБЛИЦА ДЛЯ ВЫГРУЗКИ В CSV:")
    print("="*40)
    if brain.results:
        for res in brain.results:
            print(f"{res['time']} | №{res['num']} | {res['name']}")
    else:
        print("Данные не найдены. Проверьте совпадение номеров в CSV и тесте.")