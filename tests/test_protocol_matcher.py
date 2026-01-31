import pandas as pd
import re
import os

# ========================================================
# ФУНКЦИЯ 1: Очистка строки от OCR
# ========================================================
def clean_ocr_number(raw_text):
    """
    Принимает сырой текст от OCR и превращает его в чистое число (строку).
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    # 1. Базовые замены похожих символов (регистронезависимо)
    text = raw_text.upper()
    text = text.replace('Z', '2')
    text = text.replace('O', '0')
    text = text.replace('I', '1').replace('L', '1').replace('|', '1')

    # 2. Удаляем всё, кроме цифр
    text = re.sub(r'\D', '', text)

    # 3. Убираем ведущие нули (007 -> 7)
    text = text.lstrip('0')

    # 4. Проверка условий:
    # - Если после очистки пусто
    # - Если номер "0" (в протоколе его быть не может)
    # - Если номер подозрительно длинный (больше 4 знаков)
    if text == "" or text == "0" or len(text) > 4:
        return None

    return text

# ========================================================
# ФУНКЦИЯ 2: Загрузка протокола
# ========================================================
def load_protocol(file_path):
    """
    Загружает CSV и приводит колонку number к строкам.
    """
    if not os.path.exists(file_path):
        print(f"ОШИБКА: Файл {file_path} не найден!")
        return None
    
    df = pd.read_csv(file_path)
    # Принудительно превращаем номера в строки, убирая .0 если они считались как числа
    df['number'] = df['number'].astype(str).str.replace(r'\.0$', '', regex=True)
    return df

# ========================================================
# ФУНКЦИЯ 3: Поиск совпадения
# ========================================================
def find_participant(cleaned_number, protocol_df):
    """
    Ищет номер в таблице и возвращает ФИО.
    """
    if cleaned_number is None or protocol_df is None:
        return None
    
    # Ищем строку, где номер совпадает
    result = protocol_df[protocol_df['number'] == cleaned_number]
    
    if not result.empty:
        return result.iloc[0]['name']
    return None


# ========================================================
# БЛОК ТЕСТОВ (ПЕСОЧНИЦА)
# ========================================================
if __name__ == "__main__":
    print("--- ТЕСТ 1: Очистка OCR строк ---")
    test_cases = [
        ("12", "12"),
        (" 12 ", "12"),
        ("№12", "12"),
        ("4Z", "42"),
        ("007", "7"),
        ("0", None),
        ("abc", None),
        ("12345", None)
    ]
    
    for raw, expected in test_cases:
        res = clean_ocr_number(raw)
        status = "OK" if res == expected else "FAIL"
        print(f"Ввод: '{raw}' | Итог: '{res}' | Ожидали: '{expected}' | [{status}]")

    print("\n--- ТЕСТ 2: Загрузка и поиск по протоколу ---")
    path = os.path.join("input", "protocols", "protocol_simple.csv")
    df = load_protocol(path)
    
    if df is not None:
        print("Протокол загружен успешно. Проверяем поиск:")
        
        search_tests = [
            ("12", "Петрова Мария"),
            ("42", "Сидоров Иван"),
            ("7", "Смирнов Дмитрий"),
            ("99", None)
        ]
        
        for num, expected_name in search_tests:
            name = find_participant(num, df)
            status = "OK" if name == expected_name else "FAIL"
            print(f"Поиск номера '{num}': Найдено '{name}' | [{status}]")