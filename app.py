import streamlit as st
import os
import cv2 

# Импорты твоих модулей
from src.matcher import ProtocolMatcher
from src.logic_manager import TimeLogicManager
from src.detector import ClimbingDetector
from src.video_utils import format_time, ensure_dir
from src.downloader import download_video 

# 1. Загрузка моделей
@st.cache_resource
def load_models():
    return ClimbingDetector()

def time_to_seconds(time_str):
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2: return parts[0] * 60 + parts[1]
    except: pass
    return 0

# 2. Инициализация
TEMP_DIR = "temp_data"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if 'found_timestamps' not in st.session_state:
    st.session_state['found_timestamps'] = []
if 'start_sec' not in st.session_state:
    st.session_state['start_sec'] = 0
if 'downloaded_file' not in st.session_state:
    st.session_state['downloaded_file'] = None
# НОВОЕ: запоминаем последнюю успешную ссылку и настройки обрезки
if 'last_request' not in st.session_state:
    st.session_state['last_request'] = None

st.set_page_config(page_title="Climbtag", layout="wide")
st.title("🧗‍♂️ Climbtag: автогенератор таймкодов")

detector_model = load_models()

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("1. Данные")
    uploaded_csv = st.file_uploader("Прикрепите CSV-протокол", type=['csv'])
    
    csv_path = None
    if uploaded_csv:
        csv_path = os.path.join(TEMP_DIR, "protocol.csv")
        with open(csv_path, "wb") as f:
            f.write(uploaded_csv.getbuffer())
        st.success("✅ Протокол загружен")

    st.divider()
    st.header("2. Видео")
    uploaded_video = st.file_uploader("Загрузите файл mp4", type=['mp4', 'mov', 'avi'])
    video_url = st.text_input("ИЛИ вставьте ссылку (YouTube/VK)")
    
    use_trim = False
    t_start, t_end = 0, 600
    
    if video_url and not uploaded_video:
        st.markdown("---")
        use_trim = st.checkbox("✂️ Скачать только фрагмент", value=True)
        if use_trim:
            col_t1, col_t2 = st.columns(2)
            with col_t1: t_start = st.number_input("Начало (сек)", value=0, min_value=0)
            with col_t2: t_end = st.number_input("Конец (сек)", value=600, min_value=1)

    st.divider()
    with st.expander("⚙️ Настройки анализа"):
        interval = st.slider("Интервал (сек)", 1, 10, 3)
        conf_limit = st.slider("Порог кадров", 1, 5, 3)
    
    start_btn = st.button("🚀 ЗАПУСТИТЬ АНАЛИЗ", type="primary", use_container_width=True)

# --- ЛОГИКА ОПРЕДЕЛЕНИЯ ПУТИ К ВИДЕО ---
final_video_path = None
if uploaded_video:
    final_video_path = os.path.join(TEMP_DIR, "temp_video.mp4")
    with open(final_video_path, "wb") as f:
        f.write(uploaded_video.getbuffer())
elif st.session_state['downloaded_file']:
    final_video_path = st.session_state['downloaded_file']

# --- ОСНОВНАЯ ОБЛАСТЬ ---
col_video, col_results = st.columns([2, 1])

with col_video:
    st.subheader("🎥 Плеер")
    if final_video_path:
        st.video(final_video_path, start_time=st.session_state['start_sec'])
    elif video_url:
        st.video(video_url)
    else:
        st.info("Загрузите видео, чтобы начать")

    if st.session_state['found_timestamps']:
        st.divider()
        export_text = "00:00 Начало\n" + "\n".join(
            [f"{i['time']} №{i['num']} {i['name']}" for i in st.session_state['found_timestamps']]
        )
        edited_text = st.text_area("Список таймкодов (можно править):", value=export_text, height=150)
        st.download_button("📥 Скачать .txt", edited_text, "timestamps.txt", use_container_width=True)

with col_results:
    st.subheader("⏱ Таймкоды")
    with st.container(height=500, border=True):
        live_list_placeholder = st.empty()
        
        results = st.session_state.get('found_timestamps', [])
        if results:
            with live_list_placeholder.container():
                for item in results:
                    if st.button(f"⏱️ {item['time']} — {item['name']}", key=f"btn_{item['time']}_{item['num']}", use_container_width=True):
                        st.session_state['start_sec'] = time_to_seconds(item['time'])
                        st.rerun()
        else:
            live_list_placeholder.write("Результаты появятся здесь...")

    if st.session_state['found_timestamps']:
        if st.button("🗑️ Очистить список", use_container_width=True):
            st.session_state['found_timestamps'] = []
            st.session_state['start_sec'] = 0
            st.rerun()

# --- ЛОГИКА АНАЛИЗА ---
if start_btn:
    # 1. УМНАЯ ЗАГРУЗКА
    if video_url and not uploaded_video:
        # Формируем уникальный идентификатор текущего запроса (ссылка + время обрезки)
        current_request = f"{video_url}_{t_start}_{t_end if use_trim else 'full'}"
        
        # Проверяем: нужно ли качать? (если ссылка новая ИЛИ файла нет на диске)
        need_download = (current_request != st.session_state.get('last_request')) or \
                        (not st.session_state.get('downloaded_file')) or \
                        (not os.path.exists(st.session_state['downloaded_file']))

        if need_download:
            try:
                p_bar = st.progress(0)
                status = st.empty()
                def ui_update(pct):
                    p_bar.progress(pct)
                    status.text(f"📥 Загрузка видео: {int(pct*100)}%")
                
                path, title = download_video(
                    video_url, TEMP_DIR, ui_update,
                    start_time=t_start if use_trim else None,
                    end_time=t_end if use_trim else None
                )
                
                # Запоминаем результат загрузки
                st.session_state['downloaded_file'] = path
                st.session_state['last_request'] = current_request
                final_video_path = path 
                status.success(f"✅ Загружено: {title}")
                p_bar.empty()
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
        else:
            final_video_path = st.session_state['downloaded_file']
            st.info("ℹ️ Использую уже скачанное видео (ссылка не изменилась).")

    # 2. Анализ
    if csv_path and final_video_path:
        detector = detector_model
        matcher = ProtocolMatcher(csv_path)
        brain = TimeLogicManager(conf_limit=conf_limit)
        
        cap = cv2.VideoCapture(final_video_path)
        if not cap.isOpened():
            st.error("❌ Ошибка: OpenCV не смог открыть файл.")
        else:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = (total_frames / fps) * 1000 if fps > 0 else 0
            
            p_bar_ai = st.progress(0)
            status_ai = st.empty()
            
            current_ms = 0
            st.session_state['found_timestamps'] = []
            
            while cap.isOpened():
                # ПРЕДОХРАНИТЕЛЬ: Если текущее время анализа превысило общую длительность видео,
                # принудительно останавливаем цикл. Это исправляет баг "бесконечного анализа".
                if duration > 0 and current_ms > duration:
                    break

                cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
                ret, frame = cap.read()
                
                # Если кадр не прочитан (реальный конец файла) — выходим
                if not ret: 
                    break
                
                time_str = format_time(current_ms)
                status_ai.text(f"🔍 Анализ нейросетью: {time_str}")
                
                # Поиск людей и распознавание номеров
                matches = detector.detect_and_ocr(frame, matcher)
                brain.process_frame(matches, time_str)
                
                # Обновление списка результатов (живой вывод)
                st.session_state['found_timestamps'] = brain.results.copy()
                with live_list_placeholder.container():
                    for res in brain.results:
                        st.write(f"🔍 {res['time']} — {res['name']}")
                
                # Обновление полоски прогресса
                if duration > 0:
                    # min(..., 1.0) гарантирует, что полоска не уйдет за 100%
                    p_bar_ai.progress(min(current_ms / duration, 1.0))
                
                # Переходим к следующему кадру согласно заданному интервалу
                current_ms += (interval * 1000)
            
            cap.release()
            p_bar_ai.empty()
            status_ai.success("✅ Анализ завершен!")
            st.rerun()
    else:
        st.warning("⚠️ Загрузите CSV и видео!")