class TimeLogicManager:
    """
    Класс управления логикой подтверждения атлетов.
    Фильтрует шум OCR и позволяет фиксировать повторные выступления через таймаут.
    """
    def __init__(self, conf_limit=3, session_timeout_sec=360):
        # Порог кадров для подтверждения номера
        self.conf_limit = conf_limit
        
        # Таймаут: 240 секунд = 4 минуты (как ты и просила)
        self.session_timeout_sec = session_timeout_sec
        
        # Словарь подтвержденных атлетов: {номер: последние_секунды_появления}
        self.last_confirmed_time = {} 
        
        # Словарь кандидатов: {номер: [счетчик, время_строкой, ФИО, секунды_последнего_визита]}
        self.candidates = {} 
        
        # Финальный список результатов
        self.results = []     

    def _time_to_seconds(self, time_str):
        """Улучшенная функция перевода времени в секунды (понимает MM:SS и HH:MM:SS)"""
        try:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 3: # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            return parts[0] * 60 + parts[1] # MM:SS
        except:
            return 0

    def process_frame(self, matched_list, current_time_str):
        """
        Обрабатывает список найденных номеров на текущем кадре.
        """
        current_sec = self._time_to_seconds(current_time_str)

        # --- 1. ЗАЩИТА ОТ ФАНТОМОВ ---
        # Если кандидат не появлялся в кадре более 30 секунд, мы его удаляем.
        # Это не дает случайным ошибкам (шуму) накопиться за длинную трансляцию.
        to_delete_candidates = []
        for num, data in self.candidates.items():
            # data[3] — это секунда, когда мы видели этот номер в последний раз
            if current_sec - data[3] > 60: 
                to_delete_candidates.append(num)
        
        for num in to_delete_candidates:
            del self.candidates[num]

        # --- 2. ОБРАБОТКА ТЕКУЩИХ НАХОДОК ---
        for num, name in matched_list:
            
            # Проверка таймаута (4 минуты)
            if num in self.last_confirmed_time:
                time_passed = current_sec - self.last_confirmed_time[num]
                if time_passed < self.session_timeout_sec:
                    continue
            
            if num not in self.candidates:
                # Впервые увидели: [счетчик=1, время_строкой, имя, секунды_сейчас]
                self.candidates[num] = [1, current_time_str, name, current_sec]
            else:
                # Уже был в кандидатах: наращиваем счетчик и обновляем время "последнего визита"
                self.candidates[num][0] += 1
                self.candidates[num][3] = current_sec 
                
                # Если набрали достаточно кадров для подтверждения
                if self.candidates[num][0] >= self.conf_limit:
                    first_seen_str = self.candidates[num][1] 
                    
                    self.results.append({
                        "time": first_seen_str, 
                        "num": num, 
                        "name": name
                    })
                    
                    # Запоминаем время успеха и удаляем из кандидатов
                    self.last_confirmed_time[num] = current_sec
                    del self.candidates[num]