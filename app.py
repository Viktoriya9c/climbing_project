import streamlit as st
import os
import cv2 
import gc 
import time 

# Импорты твоих модулей
from app.matcher import ProtocolMatcher
from app.logic_manager import TimeLogicManager
from app.detector import ClimbingDetector
from app.video_utils import format_time, ensure_dir
from app.downloader import download_video

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

# 2. Инициализация состояний
TEMP_DIR = "temp_data"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if 'found_timestamps' not in st.session_state: st.session_state['found_timestamps'] = []
if 'start_sec' not in st.session_state: st.session_state['start_sec'] = 0
if 'downloaded_file' not in st.session_state: st.session_state['downloaded_file'] = None
if 'last_request' not in st.session_state: st.session_state['last_request'] = None
if 'is_analyzing' not in st.session_state: st.session_state['is_analyzing'] = False

st.set_page_config(page_title="Climbtag", layout="wide")
st.title("🧗‍♂️ Climbtag: автогенератор таймкодов")

detector_model = load_models()

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("1. Протокол")
    uploaded_csv = st.file_uploader("Прикрепите CSV-протокол", type=['csv'])
    csv_path = None
    if uploaded_csv:
        csv_path = os.path.join(TEMP_DIR, "protocol.csv")
        with open(csv_path, "wb") as f: f.write(uploaded_csv.getbuffer())

    st.divider()
    st.header("2. Видео")
    
    # Способ А: Локальный файл
    uploaded_video = st.file_uploader("Загрузите файл mp4", type=['mp4', 'mov', 'avi'])
    
    # Способ Б: Ссылка
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
        
        # КНОПКА ПОДГОТОВКИ (ЭТАП 1)
        if st.button("📥 ПОДГОТОВИТЬ ВИДЕО", use_container_width=True):
            try:
                # НОВОЕ: Спиннер с твоей фразой
                with st.spinner("Загружаем видео из источника..."):
                    path, title = download_video(video_url, TEMP_DIR, lambda x: None, 
                                                 t_start if use_trim else None, 
                                                 t_end if use_trim else None)
                    st.session_state['downloaded_file'] = path
                    st.session_state['last_request'] = f"{video_url}_{t_start}_{t_end}"
                st.success(f"✅ Готово")
                st.rerun() 
            except Exception as e:
                st.error(f"Ошибка: {e}")

    # НОВОЕ: Синее инфо-поле с данными файла (Минимализм)
    if st.session_state['downloaded_file'] or uploaded_video:
        st.markdown("---")
        # Определяем путь для инфо-поля
        if uploaded_video:
            f_name = uploaded_video.name
            f_size = uploaded_video.size / (1024 * 1024)
        else:
            f_path = st.session_state['downloaded_file']
            f_name = os.path.basename(f_path)
            f_size = os.path.getsize(f_path) / (1024 * 1024)
        st.info(f"📄 {f_name} \n\n ⚖️ {f_size:.1f} МБ")

    st.divider()
    with st.expander("⚙️ Настройки анализа"):
        interval = st.slider("Интервал (сек)", 1, 10, 3)
        conf_limit = st.slider("Порог кадров", 1, 5, 3)
    
    # --- УПРАВЛЕНИЕ (ЭТАП 2) ---
    st.write("### Управление")
    video_ready = (uploaded_video is not None) or (st.session_state['downloaded_file'] is not None)
    is_running = st.session_state['is_analyzing']
    has_results = len(st.session_state['found_timestamps']) > 0
    
    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("🚀 ЗАПУСТИТЬ", type="primary", disabled=not video_ready or is_running, use_container_width=True):
            st.session_state['is_analyzing'] = True
            st.session_state['found_timestamps'] = [] 
            st.rerun()
    with col_stop:
        if st.button("🛑 СТОП", disabled=not is_running, use_container_width=True):
            st.session_state['is_analyzing'] = False
            st.rerun()
     

# --- ОПРЕДЕЛЕНИЕ ПУТИ К ВИДЕО (С ЗАЩИТОЙ SSD) ---
final_video_path = None
if uploaded_video:
    final_video_path = os.path.join(TEMP_DIR, "temp_video.mp4")
    # Перезаписываем только если файл изменился
    if not os.path.exists(final_video_path) or os.path.getsize(final_video_path) != uploaded_video.size:
        with open(final_video_path, "wb") as f: f.write(uploaded_video.getbuffer())
elif st.session_state['downloaded_file']:
    final_video_path = st.session_state['downloaded_file']

# --- ЗОНА СТАТУСА ---
status_place = st.empty()
progress_place = st.empty()

# --- ОСНОВНАЯ ОБЛАСТЬ ---
col_video, col_results = st.columns([2, 1])

with col_video:
    st.subheader("🎥 Плеер")
    # Плеер теперь виден ВСЕГДА, если есть путь к видео
    if final_video_path:
        st.video(final_video_path, start_time=st.session_state['start_sec'])
    elif video_url:
        st.info("Нажмите 'Подготовить видео' слева")
    else:
        st.info("Загрузите видео или вставьте ссылку")

    if st.session_state['found_timestamps'] and not st.session_state['is_analyzing']:
        st.divider()
        st.subheader("📝 Редактирование списка")
        export_text = "00:00 Начало\n" + "\n".join([f"{i['time']} №{i['num']} {i['name']}" for i in st.session_state['found_timestamps']])
        edited_text = st.text_area("Можно править:", value=export_text, height=150)
        st.download_button("📥 Скачать .txt", edited_text, "timestamps.txt", use_container_width=True)

with col_results:
    st.subheader("⏱ Таймкоды")
    with st.container(height=400, border=True):
        live_list_placeholder = st.empty()
        res = st.session_state.get('found_timestamps', [])
        
        if not st.session_state['is_analyzing'] and res:
            with live_list_placeholder.container():
                sorted_res = sorted(res, key=lambda x: x['name'])
                opt = ["--- Перейти к участнику ---"] + [f"⏱️ {i['time']} — {i['name']} (№{i['num']})" for i in sorted_res]
                sel = st.selectbox("Навигация:", options=opt, index=0)
                if sel != opt[0]:
                    time_part = sel.split(" — ")[0].replace("⏱️ ", "")
                    new_sec = time_to_seconds(time_part)
                    if new_sec != st.session_state['start_sec']:
                        st.session_state['start_sec'] = new_sec
                        st.rerun()
        elif st.session_state['is_analyzing']:
            # Во время анализа показываем живой список
            with live_list_placeholder.container():
                for r in res: st.write(f"🔍 {r['time']} — {r['name']}")
        else:
            live_list_placeholder.write("Результаты появятся здесь...")


# --- ЛОГИКА АНАЛИЗА ---
if st.session_state['is_analyzing']:
    if csv_path and final_video_path:
        matcher = ProtocolMatcher(csv_path)
        brain = TimeLogicManager(conf_limit=conf_limit)
        cap = cv2.VideoCapture(final_video_path)
        
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = (total_frames / fps) * 1000 if fps > 0 else 0
            
            current_ms = 0
            start_process_time = time.time()
            frames_processed = 0

            while cap.isOpened():
                if not st.session_state['is_analyzing']: break
                if duration > 0 and current_ms > duration: break

                cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
                ret, frame = cap.read()
                if not ret: break
                
                # 1. Детекция и логика
                matches = detector_model.detect_and_ocr(frame, matcher)
                brain.process_frame(matches, format_time(current_ms))
                
                # 2. Сохраняем результат в стейт
                st.session_state['found_timestamps'] = brain.results.copy()
                
                # --- ВОТ ЭТА ЧАСТЬ БЫЛА УПУЩЕНА (Живой вывод имен) ---
                with live_list_placeholder.container():
                    if st.session_state['found_timestamps']:
                        for r in st.session_state['found_timestamps']:
                            st.write(f"🔍 {r['time']} — {r['name']}")
                    else:
                        st.write("🔍 Ищем участников...")
                # ----------------------------------------------------
                
                # 3. Обновление прогресса и ETA
                frames_processed += 1
                elapsed = time.time() - start_process_time
                avg_speed = elapsed / frames_processed
                
                total_steps = duration / (interval * 1000)
                remaining_steps = total_steps - frames_processed
                eta_sec = int(remaining_steps * avg_speed)
                eta_min = max(1, (eta_sec + 30) // 60) 
                
                if duration > 0:
                    progress_place.progress(min(current_ms / duration, 1.0))
                    status_place.markdown(f"**🔍 Анализ:** {format_time(current_ms)} | **Осталось примерно:** {eta_min} мин.")
                
                current_ms += (interval * 1000)
            
            cap.release()
            gc.collect() 
            st.session_state['is_analyzing'] = False 
            st.rerun() 
    else:
        st.session_state['is_analyzing'] = False
        st.warning("⚠️ Ошибка данных!")
        st.rerun()