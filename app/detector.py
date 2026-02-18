from pathlib import Path


class DetectorUnavailableError(RuntimeError):
    pass


class PersonNumberDetector:
    def __init__(self, model_path: Path):
        try:
            from ultralytics import YOLO
            import easyocr
        except Exception as exc:
            raise DetectorUnavailableError(
                "YOLO/EasyOCR dependencies are missing. Install ultralytics easyocr opencv-python-headless."
            ) from exc

        self._YOLO = YOLO
        self._easyocr = easyocr
        self.model_path = Path(model_path)
        try:
            if self.model_path.exists():
                self.model = self._YOLO(str(self.model_path))
            else:
                # Fallback: let ultralytics resolve/download default model.
                self.model = self._YOLO("yolov8n.pt")
        except Exception as exc:
            raise DetectorUnavailableError(
                f"YOLO model unavailable: {self.model_path} (or fallback yolov8n.pt)."
            ) from exc
        # Use GPU automatically when backend supports it; easyocr handles fallback.
        self.reader = self._easyocr.Reader(["en"], gpu=False)

    def detect(self, frame, matcher):
        results = self.model(frame, verbose=False)[0]
        matched = []
        bboxes = []

        boxes = getattr(results, "boxes", None)
        if boxes is None or boxes.xyxy is None:
            return matched, bboxes

        for i, box in enumerate(boxes.xyxy):
            cls = int(boxes.cls[i])
            if cls != 0:  # person
                continue

            x1, y1, x2, y2 = map(int, box)
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = max(x1 + 1, x2)
            y2 = max(y1 + 1, y2)

            crop_y2 = y1 + (y2 - y1) // 2
            crop_back = frame[y1:crop_y2, x1:x2]
            if crop_back.size == 0:
                continue

            ocr_results = self.reader.readtext(crop_back)
            for _, text, _conf in ocr_results:
                num, name = matcher.find_participant(text)
                if not num:
                    continue

                matched.append((num, name))
                h, w = frame.shape[:2]
                bboxes.append({
                    "x": x1 / max(1, w),
                    "y": y1 / max(1, h),
                    "w": (x2 - x1) / max(1, w),
                    "h": (y2 - y1) / max(1, h),
                    "label": str(num),
                })

        return matched, bboxes
