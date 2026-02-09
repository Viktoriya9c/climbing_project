import os
import re
import pandas as pd

class ProtocolMatcher:
    """
    Класс для сопоставления текста из OCR со списком участников.
    Загружает CSV и ищет ФИО по номеру.
    """
    
    def __init__(self, file_path):
        self.db = {}
        if not os.path.exists(file_path):
            return

        try:
            # 1. Загружаем CSV
            df = self._load_csv(file_path)
            
            if df is not None:
                # 2. Строим базу данных участников
                self._build_database(df)
        except Exception:
            # Если файл совсем битый, просто оставляем базу пустой
            pass

    def _load_csv(self, file_path):
        """Пытается прочитать CSV с разными кодировками и разделителями."""
        encodings = ['utf-8', 'cp1251', 'utf-8-sig']
        for enc in encodings:
            try:
                # sep=None заставляет pandas саму угадать: запятая там или точка с запятой
                return pd.read_csv(file_path, encoding=enc, sep=None, engine='python')
            except Exception:
                continue
        return None

    def _build_database(self, df):
        """Ищет нужные колонки и заполняет словарь {номер: имя}."""
        # Приводим все заголовки к нижнему регистру для поиска
        df.columns = [str(c).lower().strip() for c in df.columns]

        # Ищем колонку с номером (перебираем варианты)
        num_col = self._find_column(df.columns, ['number', 'номер', '№', 'id', 'num'])
        # Ищем колонку с именем
        name_col = self._find_column(df.columns, ['name', 'фио', 'атлет', 'athlete', 'имя'])

        if num_col and name_col:
            for _, row in df.iterrows():
                # Чистим номер: убираем ".0", если pandas считала его как число
                raw_num = str(row[num_col]).split('.')[0].strip()
                # Убираем нули в начале (005 -> 5)
                num_val = raw_num.lstrip('0')
                if not num_val and raw_num == '0': num_val = '0' # случай если номер реально 0
                
                name_val = str(row[name_col]).strip()
                
                if num_val and name_val:
                    self.db[num_val] = name_val

    def _find_column(self, actual_cols, variants):
        """Ищет в списке колонок ту, которая похожа на одну из нужных нам."""
        for v in variants:
            if v in actual_cols:
                return v
        return None

    def find_participant(self, raw_ocr_text):
        """
        Очищает текст OCR от типичных ошибок и ищет в базе.
        Пример: 'Z10S' -> '2105' -> Петров.
        """
        if not raw_ocr_text: return None, None
        
        # 1. Базовая очистка
        text = str(raw_ocr_text).upper().strip()
        
        # 2. Заменяем буквы, которые OCR путает с цифрами
        replacements = {
            'Z': '2', 'O': '0', 'I': '1', 
            'L': '1', 'S': '5', 'B': '8', 
            'G': '6', 'T': '7'
        }
        for char, digit in replacements.items():
            text = text.replace(char, digit)
        
        # 3. Удаляем всё, кроме цифр
        text = re.sub(r'\D', '', text)
        
        # 4. Убираем нули в начале для поиска
        text = text.lstrip('0')
        
        # Если номер слишком длинный или пустой — это мусор
        if not text or len(text) > 4: 
            return None, None
        
        name = self.db.get(text)
        return (text, name) if name else (None, None)