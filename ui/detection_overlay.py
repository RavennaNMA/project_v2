# Location: project_v2/ui/detection_overlay.py
# Usage: 人臉檢測框動畫覆蓋層 - 基於 test_frame_effect 的動畫系統

import cv2
import random
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QImage, QPixmap
from PyQt6.QtCore import QTimer, pyqtSignal
from utils import AnimConfigLoader
from .cal_windows_effect import ImprovedDetectionWindowEffect, update_global_frame_count, get_global_frame_count

# 全域frame_count變數
frame_count = 0
CONTENT_ANIMATION_SPEED = 0.001

class VisualRect:
    """視覺矩形動畫類 - 完全基於參考代碼實現"""
    
    def __init__(self, x, y, w, h, config):
        self.config = config
        face_size = max(w, h)
        
        # 從配置獲取框放大倍數 (配置檔案中設定的值)
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
        # 🔧 修改：從週期配置獲取高度倍數和底部偏移
        # 載入週期配置
        from utils import ConfigLoader
        period_config = ConfigLoader().load_period_config()
        height_multiplier = period_config.get('detect_frame_height_multiplier', 1.5)
        bottom_offset_ratio = period_config.get('detect_frame_bottom_offset', 0.2)
        
        # 計算目標尺寸
        target_w = face_size * size_multiplier
        target_h = face_size * size_multiplier * height_multiplier
        
        # 計算底部偏移
        self.bottom_offset = target_h * bottom_offset_ratio
        
        #  初始化，但使用配置檔案的參數
        self.target_x = x
        self.target_y = y
        self.target_w = target_w
        self.target_h = target_h
        
        self.x = x
        self.y = y
        self.w = 0
        self.h = 0
        self.outside_w = 0
        self.outside_h = 0
        
        self.time_count = 0
        self.state = 0
        self.start_line = 0
        self.end_line = 0

        self.state1_duration = self.config.get_int('BASIC', 'state1_duration', 200)
        self.state2_duration = self.config.get_int('BASIC', 'state2_duration', 200) 
        self.state3_duration = self.config.get_int('BASIC', 'state3_duration', 60)
        self.state4_duration = self.config.get_int('BASIC', 'state4_duration', 240)
        
        # 閃爍狀態（供窗口效果同步使用）
        self.is_flickering = False
        
        # 計算累積時間點
        self.state1_end = self.state1_duration
        self.state2_end = self.state1_end + self.state2_duration
        self.state3_end = self.state2_end + self.state3_duration
        self.state4_end = self.state3_end + self.state4_duration
        
        print(f"動畫時長: State1={self.state1_duration}, State2={self.state2_duration}, State3={self.state3_duration}, State4={self.state4_duration} (總計{self.state4_end}幀)")
        
    def update(self, target_x, target_y, target_w, target_h):
        """更新邏輯 - 使用配置檔案的平滑參數"""
        # 🔧 修改：將矩形轉換為非正方形，高度更大
        face_size = max(target_w, target_h)
        
        # 從配置獲取框放大倍數
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
        # 🔧 修改：從週期配置獲取高度倍數
        # 載入週期配置
        from utils import ConfigLoader
        period_config = ConfigLoader().load_period_config()
        height_multiplier = period_config.get('detect_frame_height_multiplier', 1.5)
        
        # 計算目標尺寸
        base_size = face_size * size_multiplier
        
        #  更新目標
        self.target_x = target_x
        self.target_y = target_y
        self.target_w = base_size
        self.target_h = base_size * height_multiplier
        
        #  使用配置檔案的位置平滑參數
        position_smooth = self.config.get_float('BASIC', 'position_smooth', 0.03)
        self.x += (self.target_x - self.x) * position_smooth
        self.y += (self.target_y - self.y) * position_smooth
        
        #  時間計數
        self.time_count += 1
        
        #  使用配置檔案的狀態邏輯（支援你的700幀設計）
        if self.time_count < self.state1_end:
            self.state = 1
        elif self.time_count < self.state2_end:
            self.state = 2
        elif self.time_count < self.state3_end:
            self.state = 3
        elif self.time_count < self.state4_end:
            self.state = 4
        #  關鍵：到達最終狀態後保持在state 4，不重置
        
        #  使用配置檔案的動畫平滑參數
        if self.state == 1:
            outside_smooth = self.config.get_float('STATE1', 'outside_smooth', 0.05)
            self.outside_w += (self.target_w - self.outside_w) * outside_smooth
            self.outside_h += (self.target_h - self.outside_h) * outside_smooth
        if self.state == 2:
            outside_smooth = self.config.get_float('STATE2', 'outside_smooth', 0.05)
            inner_smooth = self.config.get_float('STATE2', 'inner_smooth', 0.04)
            self.outside_w += (self.target_w - self.outside_w) * outside_smooth
            self.outside_h += (self.target_h - self.outside_h) * outside_smooth
            self.w += (self.target_w - self.w) * inner_smooth
            self.h += (self.target_h - self.h) * inner_smooth
        if self.state == 3:
            outside_smooth = self.config.get_float('STATE3', 'outside_smooth', 0.05)
            inner_smooth = self.config.get_float('STATE3', 'inner_smooth', 0.04)
            cross_start_smooth = self.config.get_float('STATE3', 'cross_start_smooth', 0.04)
            self.outside_w += (self.target_w - self.outside_w) * outside_smooth
            self.outside_h += (self.target_h - self.outside_h) * outside_smooth
            self.w += (self.target_w - self.w) * inner_smooth
            self.h += (self.target_h - self.h) * inner_smooth
            self.start_line += (1 - self.start_line) * cross_start_smooth
        if self.state == 4:
            outside_smooth = self.config.get_float('STATE4', 'outside_smooth', 0.05)
            inner_smooth = self.config.get_float('STATE4', 'inner_smooth', 0.04)
            cross_start_smooth = self.config.get_float('STATE4', 'cross_start_smooth', 0.04)
            cross_end_smooth = self.config.get_float('STATE4', 'cross_end_smooth', 0.05)
            self.outside_w += (self.target_w - self.outside_w) * outside_smooth
            self.outside_h += (self.target_h - self.outside_h) * outside_smooth
            self.w += (self.target_w - self.w) * inner_smooth
            self.h += (self.target_h - self.h) * inner_smooth
            self.start_line += (1 - self.start_line) * cross_start_smooth
            self.end_line += (1 - self.end_line) * cross_end_smooth

    def draw(self, frame):
        """繪製邏輯 - 使用配置檔案的閃爍參數"""
        # 🔧 修復：使用預先計算的閃爍狀態，確保與窗口效果同步
        if hasattr(self, 'is_flickering'):
            show = not self.is_flickering
        else:
            # 如果沒有預先計算，則使用原有邏輯
            flicker_probability = self.config.get_float('VISUAL', 'flicker_probability', 0.2)
            show = random.random() > flicker_probability
            self.is_flickering = not show
        
        if show and (self.state in [1, 2, 3, 4]):
            # 使用設定檔中的顏色 (BGR格式)
            color = self.config.get_color_bgr()
            
            # 繪製角落線條
            self._draw_corner_lines(frame, color)
            
        # 狀態2和3: 繪製內框
        if show and (self.state in [2, 3]):
            self._draw_inner_rectangle(frame, color)
       
        # 狀態3和4: 繪製十字準星
        if show and (self.state in [3, 4]):
            self._draw_cross_lines(frame, color)

    def _draw_corner_lines(self, frame, color):
        """繪製角落線條"""
        # 使用設定參數的角落線條
        corner_length = self.config.get_float('STATE1', 'corner_length_ratio', 0.07)
        line_thickness = self.config.get_int('STATE1', 'line_thickness', 1)
        
        # 轉換為整數坐標
        center_x = int(self.x)
        center_y = int(self.y)
        half_w = int(self.outside_w * 0.5)
        half_h = int(self.outside_h * 0.5)
        corner_len_w = int(self.outside_w * corner_length)
        corner_len_h = int(self.outside_h * corner_length)
        
        # 左上角
        cv2.line(frame, 
                (center_x - half_w, center_y - half_h),
                (center_x - half_w + corner_len_w, center_y - half_h), 
                color, line_thickness)
        cv2.line(frame, 
                (center_x - half_w, center_y - half_h),
                (center_x - half_w, center_y - half_h + corner_len_h), 
                color, line_thickness)
        
        # 右上角
        cv2.line(frame, 
                (center_x + half_w, center_y - half_h),
                (center_x + half_w - corner_len_w, center_y - half_h), 
                color, line_thickness)
        cv2.line(frame, 
                (center_x + half_w, center_y - half_h),
                (center_x + half_w, center_y - half_h + corner_len_h), 
                color, line_thickness)
        
        # 右下角
        cv2.line(frame, 
                (center_x + half_w, center_y + half_h),
                (center_x + half_w - corner_len_w, center_y + half_h), 
                color, line_thickness)
        cv2.line(frame, 
                (center_x + half_w, center_y + half_h),
                (center_x + half_w, center_y + half_h - corner_len_h), 
                color, line_thickness)
        
        # 左下角
        cv2.line(frame, 
                (center_x - half_w, center_y + half_h),
                (center_x - half_w + corner_len_w, center_y + half_h), 
                color, line_thickness)
        cv2.line(frame, 
                (center_x - half_w, center_y + half_h),
                (center_x - half_w, center_y + half_h - corner_len_h), 
                color, line_thickness)

    def _draw_inner_rectangle(self, frame, color):
        """繪製內框半透明矩形"""
        # 使用配置參數
        inner_alpha = self.config.get_float('STATE2', 'inner_alpha', 50) / 255.0
        inner_size_ratio = self.config.get_float('STATE2', 'inner_size_ratio', 0.9)
        
        # 創建半透明覆蓋層
        overlay = frame.copy()
        inner_w = int(self.w * inner_size_ratio)
        inner_h = int(self.h * inner_size_ratio)
        
        cv2.rectangle(overlay,
                     (int(self.x - inner_w*0.5), int(self.y - inner_h*0.5)),
                     (int(self.x + inner_w*0.5), int(self.y + inner_h*0.5)),
                     color, -1)
        
        cv2.addWeighted(overlay, inner_alpha, frame, 1 - inner_alpha, 0, frame)

    def _draw_cross_lines(self, frame, color):
        """繪製十字準星線條"""
        # 使用配置參數
        cross_length_h = self.config.get_float('STATE3', 'cross_length_ratio_h', 0.59)
        cross_length_w = self.config.get_float('STATE3', 'cross_length_ratio_w', 0.55)
        line_thickness = self.config.get_int('STATE4', 'line_thickness', 2)
        
        # 計算十字線位置
        start_h = int(self.start_line * self.h * cross_length_h)
        end_h = int(self.end_line * self.h * cross_length_h)
        start_w = int(self.start_line * self.w * cross_length_w)
        end_w = int(self.end_line * self.w * cross_length_w)
        
        # 垂直線 - 上
        cv2.line(frame,
                (int(self.x), int(self.y - start_h)),
                (int(self.x), int(self.y - end_h)),
                color, line_thickness)
        # 垂直線 - 下
        cv2.line(frame,
                (int(self.x), int(self.y + start_h)),
                (int(self.x), int(self.y + end_h)),
                color, line_thickness)
        # 水平線 - 右
        cv2.line(frame,
                (int(self.x + start_w), int(self.y)),
                (int(self.x + end_w), int(self.y)),
                color, line_thickness)
        # 水平線 - 左
        cv2.line(frame,
                (int(self.x - start_w), int(self.y)),
                (int(self.x - end_w), int(self.y)),
                color, line_thickness)


class DetectionOverlay(QWidget):
    """檢測框覆蓋層 - 使用新動畫系統"""
    
    # 信號定義
    detection_updated = pyqtSignal(bool)  # 檢測狀態更新信號
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 載入配置
        self.anim_config = AnimConfigLoader()
        
        # 驗證配置
        config_errors = self.anim_config.validate_config()
        if config_errors:
            for key, error in config_errors.items():
                print(f"  {error}")
        
        # 初始化視覺矩形列表
        self.visual_rects = []
        
        # 初始化改進的窗口效果
        self.window_effect = ImprovedDetectionWindowEffect(
            screen_width=1080, 
            screen_height=1920, 
            config=self.anim_config
        )
        
        # 檢查是否啟用 cal windows effect
        self.cal_windows_enabled = self.anim_config.get_bool('BASIC', 'enabled', True)
    
    def update_visual_rects_main_loop(self, faces):
        """主要更新循環 - 整合 cal windows effect"""
        # 更新全域幀計數
        update_global_frame_count()
        
        # 更新視覺矩形數量
        while len(self.visual_rects) > len(faces):
            self.visual_rects.pop()
        
        while len(self.visual_rects) < len(faces):
            if len(faces) > len(self.visual_rects):
                x, y, w, h = faces[len(self.visual_rects)]
                center_x = x + w // 2
                center_y = y + h // 2
                rect = VisualRect(center_x, center_y, w, h, self.anim_config)
                self.visual_rects.append(rect)
        
        # 更新臉部狀態
        face_states = {}
        for i, (x, y, w, h) in enumerate(faces):
            if i < len(self.visual_rects):
                center_x = x + w // 2
                center_y = y + h // 2
                self.visual_rects[i].update(center_x, center_y, w, h)
                
                face_states[i] = self.visual_rects[i].state
        
        # 更新 cal windows effect（如果啟用）
        if self.cal_windows_enabled:
            self.window_effect.update_faces(faces, face_states)
            
            # 🔧 修復：先計算所有檢測框的閃爍狀態，然後同步到窗口
            for i, rect in enumerate(self.visual_rects):
                # 預先計算閃爍狀態（模擬 draw 方法中的邏輯）
                flicker_probability = self.anim_config.get_float('VISUAL', 'flicker_probability', 0.2)
                show = random.random() > flicker_probability
                rect.is_flickering = not show
                
                # 同步閃爍狀態到窗口效果
                if hasattr(rect, 'is_flickering'):
                    self.window_effect.set_flicker_state_for_face(i, rect.is_flickering)
                if i in self.window_effect.windows_by_face:
                    for window in self.window_effect.windows_by_face[i]:
                        window.set_detection_state(rect.state)
    
    def update_faces(self, faces):
        """更新臉部檢測結果"""
        self.update_visual_rects_main_loop(faces)
    
    def update_animation(self):
        """更新動畫"""
        self._update_visual_rects()
    
    def _update_visual_rects(self):
        """更新視覺矩形"""
        for rect in self.visual_rects:
            rect.update(rect.target_x, rect.target_y, rect.target_w, rect.target_h)
    
    def draw_on_frame(self, frame):
        """在幀上繪製所有效果"""
        color_bgr = self.anim_config.get_color_bgr()
        
        # 繪製視覺矩形
        for rect in self.visual_rects:
            rect.draw(frame)
        
        # 繪製 cal windows（如果啟用）
        if self.cal_windows_enabled:
            self.window_effect.draw_all_windows(frame, color_bgr)
        
        return frame
    
    def clear_detections(self):
        """清除檢測結果"""
        self.visual_rects.clear()
        if self.cal_windows_enabled:
            self.window_effect.clear_all_windows()
            # 重置 fade 狀態，確保下次檢測時 cal windows 能正常顯示
            self.window_effect.reset_fade_state()
    
    def clear_all_effects(self):
        """清除所有效果"""
        self.visual_rects.clear()
        if self.cal_windows_enabled:
            self.window_effect.clear_all_windows()
            
    def start_fade_out(self):
        """開始消失效果"""
        print("🎭 Detection Overlay 開始消失效果")
        # 清除所有檢測框和 cal windows
        self.clear_detections()
        self.clear_all_effects()
    
    def reload_config(self):
        """重新載入配置"""
        self.anim_config.reload_config()
        
        # 重新檢查是否啟用 cal windows effect
        self.cal_windows_enabled = self.anim_config.get_bool('BASIC', 'enabled', True)
        
        # 重新初始化窗口效果
        if self.cal_windows_enabled:
            self.window_effect = ImprovedDetectionWindowEffect(
                screen_width=1080, 
                screen_height=1920, 
                config=self.anim_config
            )
    
    def get_animation_info(self):
        """獲取動畫信息"""
        info = {
            'rect_count': len(self.visual_rects),
            'current_state': self.visual_rects[0].state if self.visual_rects else 0,
            'is_flickering': self.visual_rects[0].is_flickering if self.visual_rects else False
        }
        
        # 添加 cal windows 信息
        if self.cal_windows_enabled:
            info['window_count'] = self.window_effect.get_total_window_count()
            info['cal_windows_enabled'] = True
        else:
            info['window_count'] = 0
            info['cal_windows_enabled'] = False
        
        return info
    
    def enable_standalone_window_effect(self, enable=True):
        """啟用獨立窗口效果（向後兼容）"""
        self.cal_windows_enabled = enable
    
    def update_standalone_windows(self):
        """更新獨立窗口（向後兼容）"""
        if self.cal_windows_enabled:
            # 這裡可以添加額外的窗口更新邏輯
            pass
    
    def paintEvent(self, event):
        """繪製事件 - 確保透明背景"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), painter.background())
        painter.end()