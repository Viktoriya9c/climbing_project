class TimeLogicManager:
    """
    Класс управления логикой подтверждения атлетов.
    Отсеивает случайные срабатывания OCR и фиксирует время первого появления.
    """
    def __init__(self, conf_limit=3):
        # Количество кадров, на которых должен появиться номер для подтверждения
        self.conf_limit = conf_limit
        
        # Набор (set) уже зафиксированных атлетов, чтобы не обрабатывать их повторно
        self.confirmed_athletes = set() 
        
        # Словарь для хранения кандидатов: {номер: [счетчик_кадров, время_первого_появления, ФИО]}
        self.candidates = {} 
        
        # Финальный список результатов: [{"time": "...", "num": "...", "name": "..."}]
        self.results = []     

    def process_frame(self, matched_list, current_time_str):
        """
        Обрабатывает список найденных на текущем кадре номеров.
        matched_list: список кортежей [(number, name), ...]
        current_time_str: текущее время видео в формате MM:SS
        """
        for num, name in matched_list:
            # Если атлет уже был подтвержден ранее, игнорируем его
            if num in self.confirmed_athletes:
                continue 
            
            # Если номер увидели впервые — добавляем в список кандидатов
            if num not in self.candidates:
                # [1] - счетчик встреч, current_time_str - время первого контакта
                self.candidates[num] = [1, current_time_str, name]
            else:
                # Если уже видели — увеличиваем счетчик
                self.candidates[num][0] += 1
                
                # Проверяем, достиг ли кандидат порога доверия
                if self.candidates[num][0] >= self.conf_limit:
                    # Извлекаем время самого первого появления (из записи в словаре)
                    first_seen = self.candidates[num][1] 
                    
                    # Сохраняем результат в итоговый список
                    self.results.append({
                        
                        "time": first_seen, 
                        "num": num, 
                        "name": name
                    })
                    
                    # Переносим в список подтвержденных и удаляем из кандидатов
                    self.confirmed_athletes.add(num)
                    print(f"✨ ПОДТВЕРЖДЕНО: {first_seen} | №{num} {name}")
                    del self.candidates[num]