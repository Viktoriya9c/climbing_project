from src.video_utils import format_time # Понадобится для расчетов, если будем переводить в секунды

class TimeLogicManager:
    """
    Класс управления логикой подтверждения атлетов.
    Фильтрует шум OCR и позволяет фиксировать повторные выступления через таймаут.
    """
    def __init__(self, conf_limit=3, session_timeout_sec=300):
        # Порог кадров для подтверждения номера
        self.conf_limit = conf_limit
        
        # Таймаут (в секундах), через который атлет может быть зафиксирован повторно
        # 300 секунд = 5 минут
        self.session_timeout_sec = session_timeout_sec
        
        # Словарь подтвержденных атлетов: {номер: последние_секунды_появления}
        self.last_confirmed_time = {} 
        
        # Словарь кандидатов: {номер: [счетчик, время_первого_появления_строкой, ФИО, секунды]}
        self.candidates = {} 
        
        # Финальный список результатов
        self.results = []     

    def _time_to_seconds(self, time_str):
        """Вспомогательная функция для перевода MM:SS в секунды"""
        m, s = map(int, time_str.split(':'))
        return m * 60 + s

    def process_frame(self, matched_list, current_time_str):
        """
        Обрабатывает список найденных номеров на текущем кадре.
        """
        current_sec = self._time_to_seconds(current_time_str)

        for num, name in matched_list:
            
            # 1. ПРОВЕРКА ТАЙМАУТА (Повторное появление)
            if num in self.last_confirmed_time:
                time_passed = current_sec - self.last_confirmed_time[num]
                
                # Если с последнего подтверждения прошло меньше 5 минут — игнорируем
                if time_passed < self.session_timeout_sec:
                    continue
                # Если прошло больше 5 минут — значит, это новый старт, работаем дальше
            
            # 2. ЛОГИКА ПОДТВЕРЖДЕНИЯ (Кандидаты)
            if num not in self.candidates:
                # Номер увидели впервые (или впервые после таймаута)
                self.candidates[num] = [1, current_time_str, name]
            else:
                # Номер уже в кандидатах — наращиваем счетчик
                self.candidates[num][0] += 1
                
                # Если набрали достаточно кадров (conf_limit)
                if self.candidates[num][0] >= self.conf_limit:
                    first_seen_str = self.candidates[num][1] 
                    
                    # Фиксируем результат
                    self.results.append({
                        "time": first_seen_str, 
                        "num": num, 
                        "name": name
                    })
                    
                    # Запоминаем время последнего подтверждения для этого номера
                    self.last_confirmed_time[num] = current_sec
                    
                    # Очищаем из кандидатов, чтобы начать новый отсчет только через 5 минут
                    del self.candidates[num]
                    
                    # (Для отладки в консоли оставляем чистый вывод)
                    # print(f"✨ ПОДТВЕРЖДЕНО: {first_seen_str} | №{num} {name}")
                    