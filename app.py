import streamlit as st
import os
import cv2 

# Импортируем твои модули
from src.matcher import ProtocolMatcher
from src.logic_manager import TimeLogicManager
from src.detector import ClimbingDetector
from src.video_utils import format_time

# 1. Функция загрузки моделей (кэшируем)
@st.cache_resource
def load_models():
    detector = ClimbingDetector()
    return detector

# 2. Помощник для перевода времени в секунды
def time_to_seconds(time_str):
    """Превращает '01:15' в 75 секунд"""
    try:
        minutes, seconds = map(int, time_str.split(':'))
        return minutes * 60 + seconds
    except:
        return 0

# 3. Инициализация папок и памяти
if not os.path.exists("temp_data"):
    os.makedirs("temp_data")

if 'found_timestamps' not in st.session_state:
    st.session_state['found_timestamps'] = []
if 'start_sec' not in st.session_state:
    st.session_state['start_sec'] = 0

st.set_page_config(page_title="Climbing Timecoder", layout="wide")
st.title("Автогенератор таймкодов")

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("1. Загрузите протокол")
    
    # Поле для CSV
    uploaded_csv = st.file_uploader("Прикрепите CSV-протокол", type=['csv'])
    csv_path = None
    if uploaded_csv is not None:
        csv_path = os.path.join("temp_data", "protocol.csv")
        with open(csv_path, "wb") as f:
            f.write(uploaded_csv.getbuffer())
        st.success("✅ Протокол загружен")

    st.divider()
    
    st.header("2. Видео")
    # Поле для загрузки файла
    uploaded_video = st.file_uploader("Загрузите файл mp4", type=['mp4', 'mov', 'avi'])
    video_path = None
    if uploaded_video is not None:
        video_path = os.path.join("temp_data", "temp_video.mp4")
        with open(video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())
        st.success("✅ Видео загружено")

    # Поле для ссылки
    video_url = st.text_input("ИЛИ вставьте ссылку (YouTube/VK)")
    
    st.divider()
    
    # Прячем системные настройки в раскрывающийся список
    with st.expander("⚙️ Системные настройки"):
        st.write("Параметры детекции:")
        interval = st.slider("Интервал обработки (сек)", 1, 10, 3)
        conf_limit = st.slider("Порог подтверждения (кадры)", 1, 5, 3)
    
    st.divider()
    
    # Кнопка запуска
    start_btn = st.button("ЗАПУСТИТЬ АНАЛИЗ", type="primary", use_container_width=True)

# --- ОСНОВНАЯ ОБЛАСТЬ (2 Колонки) ---
col_video, col_results = st.columns([2, 1])

with col_video:
    st.subheader("Плеер")
    # Важно: параметр start_time берется из памяти сессии
    if uploaded_video:
        st.video(video_path, start_time=st.session_state['start_sec'])
    elif video_url:
        st.video(video_url, start_time=st.session_state['start_sec'])
    else:
        st.info("Загрузите видео, чтобы начать")

with col_results:
    st.subheader("Найденные таймкоды")
    
    # 1. Кнопка очистки (уже была, оставляем)
    if st.session_state['found_timestamps']:
        if st.button("🗑️ Очистить список", use_container_width=True):
            st.session_state['found_timestamps'] = []
            st.session_state['start_sec'] = 0
            st.rerun()

    # 2. Отрисовка интерактивных кнопок (для перемотки)
    results = st.session_state.get('found_timestamps', [])
    for item in results:
        label = f"⏱️ {item['time']} — {item['name']} (№{item['num']})"
        if st.button(label, key=f"btn_{item['time']}_{item['num']}", use_container_width=True):
            st.session_state['start_sec'] = time_to_seconds(item['time'])
            st.rerun()

    st.divider()

    # 3. ФОРМИРОВАНИЕ ТЕКСТА ДЛЯ ЭКСПОРТА (YouTube style)
    if results:
        st.subheader("Готовый список")
        
        # Начинаем формировать текст
        export_lines = ["00:00 Начало трансляции"]
        
        # Добавляем каждого найденного спортсмена
        for item in results:
            line = f"{item['time']} №{item['num']} {item['name']}"
            export_lines.append(line)
        
        # Соединяем все строки в один большой текст с переносами строк
        full_text = "\n".join(export_lines)
        
        # Выводим текстовое поле (из него удобно копировать одной кнопкой в углу)
        st.text_area("Скопируйте для YouTube/VK:", value=full_text, height=200)
        
        # Добавляем кнопку скачивания файла .txt
        st.download_button(
            label="📥 Скачать как .txt",
            data=full_text,
            file_name="timestamps_climbing.txt",
            mime="text/plain",
            use_container_width=True
        )

# --- ЛОГИКА АНАЛИЗА ---
if start_btn:
    if csv_path and (video_path or video_url):
        detector = load_models()
        matcher = ProtocolMatcher(csv_path)
        brain = TimeLogicManager(conf_limit=conf_limit)
        
        cap = cv2.VideoCapture(video_path if video_path else video_url)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        interval_ms = interval * 1000
        current_ms = 0
        
        # Очищаем старые результаты перед новым запуском
        st.session_state['found_timestamps'] = []
        
        while cap.isOpened():
            cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
            ret, frame = cap.read()
            if not ret:
                break
            
            time_str = format_time(current_ms)
            status_text.text(f"🔍 Анализируем: {time_str}")
            
            found_matches = detector.detect_and_ocr(frame, matcher)
            brain.process_frame(found_matches, time_str)
            
            # Сохраняем промежуточные результаты в память сессии
            st.session_state['found_timestamps'] = brain.results.copy()
            
            # Обновляем прогресс
            if video_duration_ms > 0:
                progress_pct = min(current_ms / video_duration_ms, 1.0)
                progress_bar.progress(progress_pct)
            
            current_ms += interval_ms
            
            # Чтобы список имен обновлялся прямо во время анализа, 
            # нам пришлось бы делать st.rerun(), но это прервет цикл. 
            # Поэтому в Streamlit живое обновление в цикле обычно делают через st.empty()
            # Для простоты: полные кнопки появятся сразу после завершения или 
            # мы можем добавить st.rerun() в конце.
            
        cap.release()
        progress_bar.progress(1.0)
        status_text.success("✅ Обработка завершена! Кликните на таймкод для перемотки.")
        st.rerun() # Финальное обновление, чтобы превратить текст в кнопки
        
    else:
        st.error("⚠️ Пожалуйста, загрузите и CSV-протокол, и видео-файл!")