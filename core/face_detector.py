# Location: project_v2/core/face_detector.py
# Usage: 使用 MediaPipe 進行高效能人臉偵測

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

# MediaPipe 導入（修復相容性問題）
try:
    import mediapipe as mp
    mp_face_detection = mp.solutions.face_detection
    mp_drawing = mp.solutions.drawing_utils
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: MediaPipe not available: {e}")

class FaceDetector(QObject):
    """MediaPipe 人臉偵測器"""
    
    face_detected = pyqtSignal(bool, object)  # (偵測到與否, 偵測框資訊)
    
    def __init__(self, config=None):
        super().__init__()
        
        self.config = config or {}
        
        # 檢查 MediaPipe 是否可用
        if not MEDIAPIPE_AVAILABLE:
            print("Error: MediaPipe is not available, face detection will be disabled")
            self.face_detection = None
            return
        
        # 從配置取得靈敏度
        confidence = self.config.get('detection_sensitivity', 0.5)
        
        try:
            self.face_detection = mp_face_detection.FaceDetection(
                model_selection=1,  # 1: 長距離模型 (適合廣角攝像頭)
                min_detection_confidence=confidence
            )
        except Exception as e:
            print(f"Failed to initialize MediaPipe face detection: {e}")
            self.face_detection = None
        
        self.last_detection = None
        self.main_face_id = 0
        
        # 穩定性過濾參數（平衡響應速度和穩定性）
        self.position_threshold = 3   # 位置變化閾值 - 更快跟隨
        self.size_threshold = 0.05    # 尺寸變化閾值 - 更快跟隨
        
        # 廣角攝像頭專用設置
        self.use_low_res_detection = True  # 啟用低解析度偵測
        self.min_face_area_ratio = self.config.get('min_face_area_ratio', 0.001)  # 從配置讀取最小臉部面積比例
        
    def process_frame(self, frame):
        """處理畫面並偵測人臉（恢復原始邏輯）"""
        if frame is None or self.face_detection is None:
            return None
        
        # 额外的安全检查
        if not hasattr(frame, 'shape') or len(frame.shape) < 2:
            return None
            
        try:
            # 🎯 廣角攝像頭優化：使用低解析度進行偵測
            detection_frame = frame
            scale_factor = 1.0
            
            if self.use_low_res_detection:
                detection_frame = self._prepare_detection_frame(frame)
                # 計算縮放比例，用於後續座標還原
                scale_factor = min(frame.shape[1] / detection_frame.shape[1], 
                                 frame.shape[0] / detection_frame.shape[0])
            
            # 轉換為 RGB (MediaPipe 需要)
            rgb_frame = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
            
            # 執行偵測
            results = self.face_detection.process(rgb_frame)
            
            if results and hasattr(results, 'detections') and results.detections:
                # 選擇最大的臉部 (通常是最近的)
                best_detection = self._select_main_face(results.detections, detection_frame.shape)
                
                if best_detection:
                    # 轉換為畫面座標（使用偵測畫面的尺寸）
                    bbox = self._get_bbox_coords(best_detection, detection_frame.shape)
                    
                    if bbox:
                        # 🎯 廣角攝像頭：還原到原始畫面座標
                        if self.use_low_res_detection and scale_factor > 1.0:
                            bbox = self._scale_bbox_to_original(bbox, scale_factor)
                        
                        # 🎯 過濾過小的臉部（適合廣角攝像頭）
                        if self._is_face_size_valid(bbox, frame.shape):
                            # 穩定性過濾：只有當變化足夠大時才更新
                            if self._should_update_detection(bbox):
                                self.last_detection = bbox
                                
                                self.face_detected.emit(True, bbox)
                                return bbox
                            elif self.last_detection:
                                # 使用上次的檢測結果，減少抖動
                                self.face_detected.emit(True, self.last_detection)
                                return self.last_detection
            
            # 沒有偵測到人臉
            self.last_detection = None
            self.face_detected.emit(False, None)
            return None
            
        except Exception as e:
            print(f"Face detection error: {e}")
            # 發生錯誤時，不發送偵測信號
            return None
        
    def _select_main_face(self, detections, frame_shape):
        """選擇主要追蹤的人臉"""
        if not detections:
            return None
            
        h, w = frame_shape[:2]
        best_detection = None
        max_area = 0
        
        for detection in detections:
            try:
                if hasattr(detection, 'location_data') and detection.location_data:
                    bbox = detection.location_data.relative_bounding_box
                    if bbox:
                        area = bbox.width * bbox.height * w * h
                        
                        if area > max_area:
                            max_area = area
                            best_detection = detection
            except Exception as e:
                print(f"Error processing detection: {e}")
                continue
                
        return best_detection
        
    def _prepare_detection_frame(self, frame):
        """🚀 FPS 優化：準備偵測用的低解析度畫面"""
        height, width = frame.shape[:2]
        
        # 降低解析度到 640x360 進行偵測（原本 1920x1080 的 1/3）
        target_width = 640
        target_height = 360
        
        if width > target_width or height > target_height:
            # 保持比例縮放
            scale = min(target_width / width, target_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        return frame
        
    def _get_bbox_coords(self, detection, frame_shape):
        """將相對座標轉換為絕對座標"""
        try:
            h, w = frame_shape[:2]
            
            # 安全地訪問bounding box
            if not hasattr(detection, 'location_data') or not detection.location_data:
                return None
                
            bbox = detection.location_data.relative_bounding_box
            if not bbox:
                return None
            
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)
            
            # 確保座標在畫面範圍內
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            width = min(width, w - x)
            height = min(height, h - y)
            
            # 安全地獲取confidence值
            confidence = 0.0
            try:
                if hasattr(detection, 'score') and detection.score:
                    confidence = detection.score[0] if len(detection.score) > 0 else 0.0
            except (AttributeError, IndexError, TypeError):
                confidence = 0.0
            
            return {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'confidence': confidence
            }
            
        except Exception as e:
            print(f"Error getting bbox coordinates: {e}")
            return None
    
    def _should_update_detection(self, new_bbox):
        """判斷是否應該更新檢測結果（穩定性過濾）"""
        if not self.last_detection or not new_bbox:
            return True
        
        last = self.last_detection
        
        # 檢查位置變化
        pos_diff_x = abs(new_bbox['x'] - last['x'])
        pos_diff_y = abs(new_bbox['y'] - last['y'])
        if pos_diff_x > self.position_threshold or pos_diff_y > self.position_threshold:
            return True
        
        # 檢查尺寸變化
        last_area = last['width'] * last['height']
        new_area = new_bbox['width'] * new_bbox['height']
        if last_area > 0:
            size_change = abs(new_area - last_area) / last_area
            if size_change > self.size_threshold:
                return True
        
        return False
        
    def draw_detection(self, frame, bbox):
        """在畫面上繪製偵測框 (用於測試)"""
        if bbox:
            x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # 顯示信心度
            conf_text = f"{bbox['confidence']:.2f}"
            cv2.putText(frame, conf_text, (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                       
        return frame
    
    def _scale_bbox_to_original(self, bbox, scale_factor):
        """將低解析度偵測的座標還原到原始畫面座標"""
        return {
            'x': int(bbox['x'] * scale_factor),
            'y': int(bbox['y'] * scale_factor),
            'width': int(bbox['width'] * scale_factor),
            'height': int(bbox['height'] * scale_factor),
            'confidence': bbox['confidence']
        }
    
    def _is_face_size_valid(self, bbox, frame_shape):
        """檢查臉部尺寸是否符合最小要求（廣角攝像頭適用）"""
        if not bbox:
            return False
            
        frame_area = frame_shape[0] * frame_shape[1]  # height * width
        face_area = bbox['width'] * bbox['height']
        face_area_ratio = face_area / frame_area
        
        # 檢查臉部面積是否超過最小閾值
        is_valid = face_area_ratio >= self.min_face_area_ratio
        
        if not is_valid:
            print(f"🚫 臉部過小: {face_area_ratio*100:.3f}% < {self.min_face_area_ratio*100:.1f}%")
        
        return is_valid
        
    def release(self):
        """釋放資源"""
        if hasattr(self, 'face_detection') and self.face_detection is not None:
            try:
                self.face_detection.close()
            except Exception as e:
                print(f"Error closing face detection: {e}") 
                