import streamlit as st
import os
import cv2 

# Импортируем твои обновленные модули
from src.matcher import ProtocolMatcher
from src.logic_manager import TimeLogicManager
from src.detector import ClimbingDetector
from src.video_utils import format_time, ensure_dir

# 1. Функция загрузки моделей (кэшируем ресурсы)
@st.cache_resource
def load_models():
    with st.spinner("🚀 Загрузка нейросетей Climbtag..."):
        detector = ClimbingDetector()
        return detector

# 2. Улучшенный помощник для перевода времени (теперь понимает и MM:SS, и HH:MM:SS)
def time_to_seconds(time_str):
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3:  # HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # MM:SS
            return parts[0] * 60 + parts[1]
    except Exception:
        pass
    return 0

# 3. Инициализация окружения
TEMP_DIR = "temp_data"
ensure_dir(os.path.join(TEMP_DIR, "init.txt"))

if 'found_timestamps' not in st.session_state:
    st.session_state['found_timestamps'] = []
if 'start_sec' not in st.session_state:
    st.session_state['start_sec'] = 0

st.set_page_config(page_title="Climbtag", layout="wide")
st.title("🧗‍♂️ Climbtag: автогенератор таймкодов")

# Предзагрузка моделей
detector_model = load_models()

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("1. Данные")
    uploaded_csv = st.file_uploader("Прикрепите CSV-протокол", type=['csv'])
    
    csv_path = None
    if uploaded_csv is not None:
        csv_path = os.path.join(TEMP_DIR, "protocol.csv")
        with open(csv_path, "wb") as f:
            f.write(uploaded_csv.getbuffer())
        st.success("✅ Протокол загружен")

    st.divider()
    st.header("2. Видео")
    uploaded_video = st.file_uploader("Загрузите файл mp4", type=['mp4', 'mov', 'avi'])
    
    video_path = None
    if uploaded_video is not None:
        video_path = os.path.join(TEMP_DIR, "temp_video.mp4")
        with open(video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())
        st.success("✅ Видео загружено")

    video_url = st.text_input("ИЛИ вставьте ссылку (YouTube/VK)")
    
    st.divider()
    with st.expander("⚙️ Системные настройки"):
        interval = st.slider("Интервал обработки (сек)", 1, 10, 3)
        conf_limit = st.slider("Порог подтверждения (кадры)", 1, 5, 3)
    
    st.divider()
    start_btn = st.button("🚀 ЗАПУСТИТЬ АНАЛИЗ", type="primary", use_container_width=True)

# --- ОСНОВНАЯ ОБЛАСТЬ (2 Колонки) ---
col_video, col_results = st.columns([2, 1])

with col_video:
    st.subheader("🎥 Плеер")
    # Используем либо загруженный файл, либо ссылку
    active_video = video_path if uploaded_video else (video_url if video_url else None)
    
    if active_video:
        st.video(active_video, start_time=st.session_state['start_sec'])
    else:
        st.info("Загрузите видео в боковом меню, чтобы начать")

    # Редактор под видео
    if st.session_state['found_timestamps']:
        st.divider()
        st.subheader("📝 Редактирование списка")
        
        # Сборка текста для YouTube
        export_text = "00:00 Начало трансляции\n" + "\n".join(
            [f"{item['time']} №{item['num']} {item['name']}" for item in st.session_state['found_timestamps']]
        )
        
        edited_text = st.text_area("Исправьте ошибки перед скачиванием:", value=export_text, height=200)
        
        st.download_button(
            label="📥 Скачать исправленный список (.txt)",
            data=edited_text,
            file_name="timestamps_final.txt",
            mime="text/plain",
            use_container_width=True
        )

with col_results:
    st.subheader("⏱ Таймкоды")
    
    with st.container(height=500, border=True):
        live_list_placeholder = st.empty()
        
        results = st.session_state.get('found_timestamps', [])
        
        if results:
            with live_list_placeholder.container():
                for item in results:
                    label = f"⏱️ {item['time']} — {item['name']} (№{item['num']})"
                    if st.button(label, key=f"btn_{item['time']}_{item['num']}", use_container_width=True):
                        st.session_state['start_sec'] = time_to_seconds(item['time'])
                        st.rerun()
        else:
            live_list_placeholder.write("Список пуст. Запустите анализ.")

    if results:
        if st.button("🗑️ Очистить всё", use_container_width=True):
            st.session_state['found_timestamps'] = []
            st.session_state['start_sec'] = 0
            st.rerun()

# --- ЛОГИКА АНАЛИЗА ---
if start_btn:
    if csv_path and active_video:
        detector = detector_model
        matcher = ProtocolMatcher(csv_path)
        brain = TimeLogicManager(conf_limit=conf_limit)
        
        cap = cv2.VideoCapture(active_video)
        if not cap.isOpened():
            st.error("❌ Не удалось открыть видео")
        else:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            interval_ms = interval * 1000
            current_ms = 0
            st.session_state['found_timestamps'] = []
            
            while cap.isOpened():
                cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
                ret, frame = cap.read()
                if not ret:
                    break
                
                time_str = format_time(current_ms)
                status_text.text(f"🔍 Анализ: {time_str}")
                
                # Поиск и распознавание
                found_matches = detector.detect_and_ocr(frame, matcher)
                brain.process_frame(found_matches, time_str)
                
                # Обновление состояния и живого списка
                st.session_state['found_timestamps'] = brain.results.copy()
                with live_list_placeholder.container():
                    for res in brain.results:
                        st.write(f"🔍 {res['time']} — {res['name']}")
                
                # Прогресс
                if video_duration_ms > 0:
                    progress_pct = min(current_ms / video_duration_ms, 1.0)
                    progress_bar.progress(progress_pct)
                
                current_ms += interval_ms
                
            cap.release()
            progress_bar.progress(1.0)
            status_text.success("✅ Анализ завершен!")
            st.rerun()
    else:
        st.error("⚠️ Загрузите CSV-протокол и укажите видео!")