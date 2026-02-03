import os
import re
import pandas as pd

class ProtocolMatcher:
    """Класс для сопоставления текста из OCR со списком участников в CSV."""
    
    def __init__(self, file_path):
        self.db = {}
        if not os.path.exists(file_path):
            print(f"❌ Файл протокола не найден: {file_path}")
            return

        # Пробуем разные кодировки для корректного чтения CSV
        df = None
        encodings = ['utf-8', 'cp1251', 'utf-8-sig']
        for enc in encodings:
            try:
                # sep=None и engine='python' позволяют автоматически определить разделитель (запятая или точка с запятой)
                df = pd.read_csv(file_path, encoding=enc, sep=None, engine='python')
                break
            except Exception:
                continue
        
        if df is not None:
            # Очищаем заголовки и заполняем базу данных {номер: имя}
            df.columns = [c.lower().strip() for c in df.columns]
            for _, row in df.iterrows():
                num_val = str(row['number']).split('.')[0].strip()
                name_val = str(row['name']).strip()
                self.db[num_val] = name_val
            print(f"✅ Протокол загружен: {len(self.db)} участников.")

    def find_participant(self, raw_ocr_text):
        """Очищает текст от мусора и ищет номер в базе данных."""
        if not raw_ocr_text: return None, None
        
        # Очистка: в верхний регистр, замена похожих символов, удаление не-цифр
        text = str(raw_ocr_text).upper()
        text = text.replace('Z', '2').replace('O', '0').replace('I', '1').replace('L', '1')
        text = re.sub(r'\D', '', text).lstrip('0')
        
        # Если после очистки ничего не осталось или число слишком длинное — это мусор
        if text == "" or len(text) > 4: return None, None
        
        name = self.db.get(text)
        return (text, name) if name else (None, None)