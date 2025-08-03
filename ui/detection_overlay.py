# Location: project_v2/ui/detection_overlay.py
# Usage: 人臉檢測框動畫覆蓋層 - 基於 test_frame_effect 的動畫系統

import cv2
import random
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QImage, QPixmap
from PyQt6.QtCore import QTimer, pyqtSignal
from utils import AnimConfigLoader
from .cal_windows_effect import DetectionWindowEffect, MIN_LIFE, MAX_LIFE, SPAWN_RATE


class VisualRect:
    """視覺矩形動畫類 - 完全基於參考代碼實現"""
    
    def __init__(self, x, y, w, h, config):
        self.config = config
        face_size = max(w, h)
        
        # 從配置獲取框放大倍數 (配置檔案中設定的值)
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
        # 🔧 修正：使用正方形尺寸
        target_w = face_size * size_multiplier
        target_h = face_size * size_multiplier
        
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
        # 🔧 修正：將矩形轉換為正方形，以較大的邊為基準
        face_size = max(target_w, target_h)
        
        # 從配置獲取框放大倍數
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
        # 🔧 修正：使用正方形尺寸
        square_size = face_size * size_multiplier
        
        #  更新目標
        self.target_x = target_x
        self.target_y = target_y
        self.target_w = square_size
        self.target_h = square_size
        
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
        #  使用配置檔案的閃爍機率
        flicker_probability = self.config.get_float('VISUAL', 'flicker_probability', 0.2)
        show = random.random() > flicker_probability
        
        # 保存閃爍狀態供窗口效果使用
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
        
        # 載入動畫配置
        self.anim_config = AnimConfigLoader()
        
        # 驗證配置
        config_errors = self.anim_config.validate_config()
        if config_errors:
            print("動畫配置警告:")
            for key, error in config_errors.items():
                print(f"  {error}")
        
        # 檢測框列表
        self.visual_rects = []
        
        # 科技感窗口效果管理器
        self.window_effect = DetectionWindowEffect(screen_width=1280, screen_height=720)
        
        # 當前檢測到的人臉
        self.current_faces = []
        self.has_faces = False
        
        # 性能統計
        self.frame_count = 0
        self.last_fps_update = 0
        self.fps = 0
        
        print(f"檢測框動畫初始化完成，使用主循環更新模式，支援高品質700幀動畫（60 FPS）")
        print(f"科技感窗口效果已啟用，支援以檢測框為中心的動態窗口動畫")
        print(f"窗口生命週期: {MIN_LIFE}-{MAX_LIFE} 幀，生成率: {SPAWN_RATE*100:.1f}%")
        print(f"獨立模式可用 - 調用 enable_standalone_window_effect(True) 啟用LLM載入效果")
    
    def update_visual_rects_main_loop(self, faces):
        """主循環更新方法 - 完全按照參考代碼邏輯"""
        # 更新檢測狀態
        new_has_faces = len(faces) > 0
        if new_has_faces != self.has_faces:
            self.has_faces = new_has_faces
            self.detection_updated.emit(self.has_faces)
        
        # 更新視覺效果矩形
        while len(self.visual_rects) > len(faces):
            self.visual_rects.pop()
        while len(self.visual_rects) < len(faces):
            if len(faces) > len(self.visual_rects):
                x, y, w, h = faces[len(self.visual_rects)]
                # 轉換為中心點座標
                center_x = x + w // 2
                center_y = y + h // 2
                rect = VisualRect(center_x, center_y, w, h, self.anim_config)
                self.visual_rects.append(rect)
                print(f"創建新的檢測框動畫 (總數: {len(self.visual_rects)})")
        
        for i, (x, y, w, h) in enumerate(faces):
            if i < len(self.visual_rects):
                # 轉換為中心點座標
                center_x = x + w // 2
                center_y = y + h // 2
                self.visual_rects[i].update(center_x, center_y, w, h)
        
        # 更新當前人臉列表
        self.current_faces = faces
        
        # 更新科技感窗口效果
        self.window_effect.update_faces(faces)
        
        # 更新獨立模式（如果啟用）
        self.window_effect.update_standalone_mode()
        
        # 同步檢測框與窗口的閃爍狀態
        for i, rect in enumerate(self.visual_rects):
            if hasattr(rect, 'is_flickering'):
                self.window_effect.set_flicker_state_for_face(i, rect.is_flickering)
                # 同時同步獨立模式的閃爍狀態
                self.window_effect.set_standalone_flicker_state(rect.is_flickering)
        
        # 更新FPS統計
        self.frame_count += 1
        import time
        current_time = time.time()
        if current_time - self.last_fps_update >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_update = current_time
    
    def update_faces(self, faces):
        """保留的相容性方法 - 重定向到主循環更新"""
        self.update_visual_rects_main_loop(faces)
    
    def update_animation(self):
        """移除獨立動畫更新 - 現在在主循環中統一處理"""
        # 這個方法現在只用於調試，實際更新在 update_visual_rects_main_loop 中
        pass
    
    def _update_visual_rects(self):
        """移除獨立的矩形更新 - 現在在主循環中統一處理"""
        # 這個方法不再需要，所有更新邏輯都在 update_visual_rects_main_loop 中
        pass
    
    def draw_on_frame(self, frame):
        """在OpenCV幀上繪製檢測框和科技感窗口效果"""
        if not self.visual_rects:
            return frame
        
        # 獲取顏色配置
        color_bgr = self.anim_config.get_color_bgr()
        
        # 為每個視覺矩形繪製動畫
        for rect in self.visual_rects:
            rect.draw(frame)
        
        # 繪製科技感窗口效果
        self.window_effect.draw_all_windows(frame, color_bgr)
        
        return frame
    
    def clear_detections(self):
        """清除所有檢測框和人臉相關窗口效果 - 保留獨立模式窗口"""
        self.update_visual_rects_main_loop([])  # 空的人臉列表
        # 只清除人臉相關的窗口，保留獨立模式的窗口
        self.window_effect.windows_by_face.clear()
        self.window_effect.center_points_by_face.clear()
    
    def clear_all_effects(self):
        """清除所有效果（包括獨立模式）"""
        self.update_visual_rects_main_loop([])  # 空的人臉列表
        self.window_effect.clear_all_windows()  # 清除所有窗口效果
        self.window_effect.enable_standalone_mode(False)  # 禁用獨立模式
    
    def reload_config(self):
        """重新載入動畫配置 - 不重置動畫進度"""
        print("重新載入檢測框動畫配置...")
        self.anim_config.reload_config()
        
        # 驗證新配置
        config_errors = self.anim_config.validate_config()
        if config_errors:
            print("動畫配置警告:")
            for key, error in config_errors.items():
                print(f"  {error}")
        
        for rect in self.visual_rects:
            rect.config = self.anim_config
        
        print(f"配置重載完成，動畫狀態保持不變")
    
    def get_animation_info(self):
        """獲取動畫信息"""
        # 從第一個矩形獲取總時長
        total_duration = 700  # 預設值
        if self.visual_rects:
            total_duration = self.visual_rects[0].state4_end
            
        info = {
            'total_rects': len(self.visual_rects),
            'animation_fps': self.fps,
            'total_duration': total_duration,  # 使用配置檔案的實際總時長
            'has_faces': self.has_faces,
            'total_windows': self.window_effect.get_total_window_count()  # 科技感窗口總數
        }
        
        if self.visual_rects:
            rect = self.visual_rects[0]  # 取第一個矩形的狀態
            info.update({
                'current_state': rect.state,
                'time_count': rect.time_count,
                'animation_progress': min(100, (rect.time_count / total_duration) * 100)  # 基於實際總時長
            })
        
        return info
    
    def enable_standalone_window_effect(self, enable=True):
        """啟用/禁用獨立窗口效果（用於LLM載入等場景）"""
        self.window_effect.enable_standalone_mode(enable)
    
    def update_standalone_windows(self):
        """獨立更新窗口效果（不依賴人臉檢測）"""
        self.window_effect.update_standalone_mode()
        
        # 更新FPS統計
        self.frame_count += 1
        import time
        current_time = time.time()
        if current_time - self.last_fps_update >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_update = current_time
        
    def paintEvent(self, event):
        """PyQt繪製事件 - 目前主要用於調試"""
        super().paintEvent(event)
        # 這裡可以添加額外的PyQt繪製邏輯，但主要繪製在OpenCV幀上進行