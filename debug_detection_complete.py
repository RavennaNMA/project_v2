# Location: project_v2/debug_detection_complete.py
# Usage: 調試工具 - 使用與主程序完全相同的組件

import sys
import cv2
import numpy as np
import time
import random
import math
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

# 簡單測試
print("🔧 開始載入調試工具...")

# 導入主程序的實際組件 (避免完整依賴鏈)
import sys
import os

# 添加項目根目錄到路徑
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 直接導入特定文件避免依賴問題
from utils.anim_config_loader import AnimConfigLoader

# 直接導入DetectionWindowEffect文件避免ui模組依賴
import importlib.util
spec = importlib.util.spec_from_file_location("cal_windows_effect", "ui/cal_windows_effect.py")
cal_windows_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cal_windows_module)
DetectionWindowEffect = cal_windows_module.DetectionWindowEffect

# 全域frame_count變數 - 參考原始代碼
frame_count = 0

# 內容動畫基礎速度 (對應Processing的frameCount*0.1)
CONTENT_ANIMATION_SPEED = 0.1

# Processing風格噪聲 - 參考原始代碼
class ProcessingStyleNoise:
    def __init__(self):
        self.noise_table = {}
        self.random_seed = random.randint(0, 10000)
        
    def noise(self, x, y=0, z=0):
        # 離散化座標產生跳動效果
        grid_size = 0.5
        x_grid = int(x / grid_size)
        y_grid = int(y / grid_size) 
        z_grid = int(z / grid_size)
        
        x_fract = (x / grid_size) - x_grid
        y_fract = (y / grid_size) - y_grid
        z_fract = (z / grid_size) - z_grid
        
        def grid_random(gx, gy, gz):
            # 使用hash函數產生偽隨機數，避免修改全域random狀態
            seed = (gx * 73856093) ^ (gy * 19349663) ^ (gz * 83492791) ^ self.random_seed
            # 使用簡單的線性同餘生成器
            a = 1664525
            c = 1013904223
            m = 2**32
            return ((a * seed + c) % m) / m
        
        # 8個角點的值
        v000 = grid_random(x_grid, y_grid, z_grid)
        v001 = grid_random(x_grid, y_grid, z_grid + 1)
        v010 = grid_random(x_grid, y_grid + 1, z_grid)
        v011 = grid_random(x_grid, y_grid + 1, z_grid + 1)
        v100 = grid_random(x_grid + 1, y_grid, z_grid)
        v101 = grid_random(x_grid + 1, y_grid, z_grid + 1)
        v110 = grid_random(x_grid + 1, y_grid + 1, z_grid)
        v111 = grid_random(x_grid + 1, y_grid + 1, z_grid + 1)
        
        def sharp_interp(t):
            return t * t * (3.0 - 2.0 * t)
        
        x_fract = sharp_interp(x_fract)
        y_fract = sharp_interp(y_fract)
        z_fract = sharp_interp(z_fract)
        
        # 三線性插值
        v00 = v000 * (1 - x_fract) + v100 * x_fract
        v01 = v001 * (1 - x_fract) + v101 * x_fract
        v10 = v010 * (1 - x_fract) + v110 * x_fract
        v11 = v011 * (1 - x_fract) + v111 * x_fract
        
        v0 = v00 * (1 - y_fract) + v10 * y_fract
        v1 = v01 * (1 - y_fract) + v11 * y_fract
        
        result = v0 * (1 - z_fract) + v1 * z_fract
        result = (result - 0.5) * 1 + 0.3
        
        return max(0, min(1, result))

# 建立全域 noise 物件
perlin = ProcessingStyleNoise()

def pde_noise(x, y=0, z=0):
    """模擬Processing的noise函數"""
    return perlin.noise(x, y, z)

# 視覺矩形動畫類 (從主程序複製)
class VisualRect:
    """視覺矩形動畫類 - 完全基於主程序實現"""
    
    def __init__(self, x, y, w, h, config):
        self.config = config
        face_size = max(w, h)
        
        # 從配置獲取框放大倍數
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
        # 使用正方形尺寸
        target_w = face_size * size_multiplier
        target_h = face_size * size_multiplier
        
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
        
        # 閃爍狀態
        self.is_flickering = False
        
        # 計算累積時間點
        self.state1_end = self.state1_duration
        self.state2_end = self.state1_end + self.state2_duration
        self.state3_end = self.state2_end + self.state3_duration
        self.state4_end = self.state3_end + self.state4_duration
        
    def update(self, target_x, target_y, target_w, target_h):
        """更新邏輯"""
        face_size = max(target_w, target_h)
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        square_size = face_size * size_multiplier
        
        self.target_x = target_x
        self.target_y = target_y
        self.target_w = square_size
        self.target_h = square_size
        
        position_smooth = self.config.get_float('BASIC', 'position_smooth', 0.03)
        self.x += (self.target_x - self.x) * position_smooth
        self.y += (self.target_y - self.y) * position_smooth
        
        self.time_count += 1
        
        if self.time_count < self.state1_end:
            self.state = 1
        elif self.time_count < self.state2_end:
            self.state = 2
        elif self.time_count < self.state3_end:
            self.state = 3
        elif self.time_count < self.state4_end:
            self.state = 4
        
        # 狀態特定更新
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
        """繪製邏輯"""
        flicker_probability = self.config.get_float('VISUAL', 'flicker_probability', 0.2)
        show = random.random() > flicker_probability
        
        self.is_flickering = not show
        
        if show and (self.state in [1, 2, 3, 4]):
            color = self.config.get_color_bgr()
            self._draw_corner_lines(frame, color)
            
        if show and (self.state in [2, 3]):
            self._draw_inner_rectangle(frame, color)
       
        if show and (self.state in [3, 4]):
            self._draw_cross_lines(frame, color)

    def _draw_corner_lines(self, frame, color):
        """繪製角落線條"""
        corner_length = self.config.get_float('STATE1', 'corner_length_ratio', 0.07)
        line_thickness = self.config.get_int('STATE1', 'line_thickness', 1)
        
        center_x = int(self.x)
        center_y = int(self.y)
        half_w = int(self.outside_w * 0.5)
        half_h = int(self.outside_h * 0.5)
        corner_len_w = int(self.outside_w * corner_length)
        corner_len_h = int(self.outside_h * corner_length)
        
        # 四個角的線條
        cv2.line(frame, (center_x - half_w, center_y - half_h),
                (center_x - half_w + corner_len_w, center_y - half_h), color, line_thickness)
        cv2.line(frame, (center_x - half_w, center_y - half_h),
                (center_x - half_w, center_y - half_h + corner_len_h), color, line_thickness)
        
        cv2.line(frame, (center_x + half_w, center_y - half_h),
                (center_x + half_w - corner_len_w, center_y - half_h), color, line_thickness)
        cv2.line(frame, (center_x + half_w, center_y - half_h),
                (center_x + half_w, center_y - half_h + corner_len_h), color, line_thickness)
        
        cv2.line(frame, (center_x + half_w, center_y + half_h),
                (center_x + half_w - corner_len_w, center_y + half_h), color, line_thickness)
        cv2.line(frame, (center_x + half_w, center_y + half_h),
                (center_x + half_w, center_y + half_h - corner_len_h), color, line_thickness)
        
        cv2.line(frame, (center_x - half_w, center_y + half_h),
                (center_x - half_w + corner_len_w, center_y + half_h), color, line_thickness)
        cv2.line(frame, (center_x - half_w, center_y + half_h),
                (center_x - half_w, center_y + half_h - corner_len_h), color, line_thickness)

    def _draw_inner_rectangle(self, frame, color):
        """繪製內框半透明矩形"""
        inner_alpha = self.config.get_float('STATE2', 'inner_alpha', 50) / 255.0
        inner_size_ratio = self.config.get_float('STATE2', 'inner_size_ratio', 0.9)
        
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
        cross_length_h = self.config.get_float('STATE3', 'cross_length_ratio_h', 0.59)
        cross_length_w = self.config.get_float('STATE3', 'cross_length_ratio_w', 0.55)
        line_thickness = self.config.get_int('STATE4', 'line_thickness', 2)
        
        start_h = int(self.start_line * self.h * cross_length_h)
        end_h = int(self.end_line * self.h * cross_length_h)
        start_w = int(self.start_line * self.w * cross_length_w)
        end_w = int(self.end_line * self.w * cross_length_w)
        
        # 十字線
        cv2.line(frame, (int(self.x), int(self.y - start_h)),
                (int(self.x), int(self.y - end_h)), color, line_thickness)
        cv2.line(frame, (int(self.x), int(self.y + start_h)),
                (int(self.x), int(self.y + end_h)), color, line_thickness)
        cv2.line(frame, (int(self.x + start_w), int(self.y)),
                (int(self.x + end_w), int(self.y)), color, line_thickness)
        cv2.line(frame, (int(self.x - start_w), int(self.y)),
                (int(self.x - end_w), int(self.y)), color, line_thickness)

# 改進的窗口效果類 - 參考原始 cal_windows.py
class ImprovedCalWindow:
    """改進的窗口類 - 參考原始 cal_windows.py 實現"""
    
    def __init__(self, center_x, center_y, face_size):
        # 初始化位置固定相關屬性
        self.position_fixed = False
        self.fixed_x = None
        self.fixed_y = None
        
        self.center_x = center_x
        self.center_y = center_y
        self.face_size = face_size
        
        # 保存生成點（連接線的目標點）
        self.spawn_center_x = center_x
        self.spawn_center_y = center_y
        
        # 視窗屬性 - 參考原始代碼，但加入大小和透明度隨機化
        base_width = 160
        base_height = 100
        size_multiplier = random.uniform(1.0, 1.2)  # 1.0-1.2倍大小變化
        self.width = int(base_width * size_multiplier)
        self.height = int(base_height * size_multiplier)
        
        # 透明度隨機化：最小150，最大255
        self.base_alpha = random.randint(150, 255)
        
        self.window_kind = random.randint(1, 16)  # 原始 WINDOW_TYPES
        self.life = random.randint(200, 400)  # 原始 MIN_LIFE, MAX_LIFE
        self.max_life = self.life
        self.display = True
        
        # 極座標位置 - 確保在檢測框外但可見範圍內
        # 增加最小距離，確保窗口遠離檢測框
        min_radius = max(face_size * 2, 200)  # 至少距離檢測框1.5倍大小
        # 確保max_radius不會小於min_radius
        screen_distance = min(center_x, center_y, 1080-center_x, 1920-center_y)
        max_radius = max(min_radius + 100, min(400, screen_distance * 0.9))
        self.r = random.uniform(min_radius, max_radius)
        self.theta = random.uniform(0, 360)
        self.phi = random.uniform(-25, 25)  # 原始 MAX_PHI
        
        self.update_position()
        
        # 動畫屬性 - 參考原始代碼
        self.i = random.randint(0, 1000)
        self.alpha = 1.0
        self.mode = 3
        
        # 連接線偏移 - 簡化為單一直線
        self.connection_offset_x = random.uniform(-20, 20)  # 減少偏移範圍
        self.connection_offset_y = random.uniform(-15, 15)  # 減少偏移範圍
        self.quadrant = random.randint(0, 3)
        
        self.force_flicker = False
        
        # 新增：檢測框狀態跟踪
        self.detection_state = 0  # 默認狀態為0
        
    def update_position(self):
        """更新窗口位置 - 基於生成點計算位置"""
        try:
            rad_theta = math.radians(self.theta)
            rad_phi = math.radians(self.phi)
            
            # 確保生成點已初始化
            if not hasattr(self, 'spawn_center_x') or not hasattr(self, 'spawn_center_y'):
                # 如果生成點未初始化，使用檢測框中心
                self.x = self.center_x + self.r * math.cos(rad_theta) * math.cos(rad_phi)
                self.y = self.center_y + self.r * math.sin(rad_theta) * math.cos(rad_phi)
            else:
                # 基於生成點計算窗口位置
                self.x = self.spawn_center_x + self.r * math.cos(rad_theta) * math.cos(rad_phi)
                self.y = self.spawn_center_y + self.r * math.sin(rad_theta) * math.cos(rad_phi)
            
            # 確保窗口在屏幕範圍內
            self.x = max(self.width//2, min(1080 - self.width//2, self.x))
            self.y = max(self.height//2, min(1920 - self.height//2, self.y))
            
            # 額外檢查：確保窗口不會與檢測框重疊
            if hasattr(self, 'center_x') and hasattr(self, 'center_y') and hasattr(self, 'face_size'):
                frame_half_size = self.face_size * 0.65  # 檢測框的一半大小
                frame_left = self.center_x - frame_half_size
                frame_right = self.center_x + frame_half_size
                frame_top = self.center_y - frame_half_size
                frame_bottom = self.center_y + frame_half_size
                
                # 窗口的邊界
                window_left = self.x - self.width//2
                window_right = self.x + self.width//2
                window_top = self.y - self.height//2
                window_bottom = self.y + self.height//2
                
                # 如果窗口與檢測框重疊，重新調整位置
                if (window_right > frame_left and window_left < frame_right and 
                    window_bottom > frame_top and window_top < frame_bottom):
                    # 將窗口移到更遠的位置
                    self.r = max(self.r + 50, self.face_size * 2.0)
                    self.update_position()
                    
            # 固定窗口位置（只在第一次設置）
            if not self.position_fixed:
                self.fixed_x = self.x
                self.fixed_y = self.y
                self.position_fixed = True
                
        except Exception as e:
            print(f"窗口位置更新錯誤: {e}")
            # 使用安全的默認值
            self.x = 540  # 屏幕中心
            self.y = 960
    
    def update_center(self, new_center_x, new_center_y):
        """更新中心點位置 - 只更新生成點，窗口位置保持固定"""
        # 更新檢測框中心（用於碰撞檢測）
        self.center_x = new_center_x
        self.center_y = new_center_y
        
        # 更新生成點位置（讓生成點跟隨檢測框移動）
        self.spawn_center_x = new_center_x
        self.spawn_center_y = new_center_y
        
        # 窗口位置保持固定，不更新
        if self.position_fixed:
            self.x = self.fixed_x
            self.y = self.fixed_y
        
    def set_force_flicker(self, should_flicker):
        self.force_flicker = should_flicker
        
    def set_detection_state(self, state):
        """設置檢測框狀態"""
        self.detection_state = state
        
    def update(self):
        """更新窗口狀態 - 參考原始代碼的模式系統"""
        global frame_count
        
        self.life -= 1  # 原始 LIFE_DECAY
        
        # 更新模式 - 完全參考原始代碼
        if self.life >= self.max_life * 0.8:
            self.mode = 3
        elif self.life >= self.max_life * 0.2:
            self.mode = 2
        elif self.life > 0:
            self.mode = 1
        else:
            self.mode = 0
            
        # 根據模式和強制閃爍更新顯示狀態 - 參考原始代碼
        if self.force_flicker:
            self.display = False
            self.alpha = 0.0
        elif self.mode == 3:  # 初始閃爍
            self.display = (self.life % 2 == 0)
            self.alpha = 1.0
        elif self.mode == 2:  # 正常顯示
            self.display = True
            self.alpha = 1.0
        elif self.mode == 1:  # 結束閃爍
            self.display = (self.life % 2 == 0)
            self.alpha = 1.0
        else:
            self.display = False
            self.alpha = 0.0
            
        return self.life > 0
    
    def draw_on_cv_frame(self, frame, color_bgr=(255, 255, 255)):
        """在OpenCV幀上繪製窗口 - 參考原始代碼的繪製邏輯"""
        # 檢查檢測框狀態，只有在狀態3或更高時才顯示窗口
        if self.detection_state < 3:
            return
            
        if not self.display:
            return
            
        alpha_int = int(255 * self.alpha)
        
        # 繪製連接線 - 簡化為單一直線
        connection_alpha = int(50 * self.alpha)  # 原始：50*Enter_Light
        connection_color = tuple(int(c * connection_alpha / 255) for c in color_bgr)
        
        # 單一直線連接窗口到生成點
        cv2.line(frame, 
                (int(self.x), int(self.y)), 
                (int(self.spawn_center_x), int(self.spawn_center_y)), 
                connection_color, 1)
        # 調試：在生成點位置畫一個小圓圈
        cv2.circle(frame, (int(self.spawn_center_x), int(self.spawn_center_y)), 3, (0, 255, 0), -1)
        
        # 繪製窗口框架 - 使用自定義透明度
        frame_alpha = int(self.base_alpha * self.alpha)  # 使用自定義透明度
        window_color = tuple(int(c * frame_alpha / 255) for c in color_bgr)
        
        # 主視窗框架
        wx = int(self.x - self.width/2)
        wy = int(self.y - self.height/2)
        cv2.rectangle(frame, (wx, wy), (wx + self.width, wy + self.height), window_color, 1)
        
        # 內框 - 參考原始代碼
        inner_x = int(self.x - self.width * 0.46)
        inner_y = int(self.y - self.height * 0.4)
        inner_w = int(self.width * 0.92)
        inner_h = int(self.height * 0.8)
        cv2.rectangle(frame, (inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h), window_color, 1)
        
        # 標題欄按鈕 - 參考原始代碼
        cv2.rectangle(frame, (wx + 6, wy + 3), (wx + 12, wy + 9), window_color, 1)
        cv2.rectangle(frame, (wx + 20, wy + 3), (wx + 26, wy + 9), window_color, 1)
        
        # 繪製內容 - 簡化版本
        self.draw_content_on_cv(frame, int(self.x), int(self.y), window_color)
        
    def draw_content_on_cv(self, frame, cx, cy, color):
        """繪製窗口內容 - 完整實現16種類型，與原始 cal_windows.py 相同"""
        global frame_count
        
        # 使用與原始代碼相同的座標系統（相對於窗口中心）
        if self.window_kind == 1:      # Bar chart
            self.draw_bar_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 2:    # Line chart with points
            self.draw_line_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 3:    # Curve chart with vertical lines
            self.draw_curve_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 4:    # Matrix display
            self.draw_matrix_display_cv(frame, cx, cy, color)
        elif self.window_kind == 5:    # Geometric pattern (8 triangles)
            self.draw_geometric_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 6:    # Grid pattern
            self.draw_grid_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 7:    # Oscilloscope
            self.draw_oscilloscope_cv(frame, cx, cy, color)
        elif self.window_kind == 8:    # Radar pattern
            self.draw_radar_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 9:    # Complex rotating shapes
            self.draw_complex_shapes_cv(frame, cx, cy, color)
        elif self.window_kind == 10:   # Crosshair pattern
            self.draw_crosshair_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 11:   # Diamond and trapezoid shapes
            self.draw_diamond_shapes_cv(frame, cx, cy, color)
        elif self.window_kind == 12:   # Level indicators with circles
            self.draw_level_indicators_cv(frame, cx, cy, color)
        elif self.window_kind == 13:   # Progress bars
            self.draw_progress_bars_cv(frame, cx, cy, color)
        elif self.window_kind == 14:   # Vertical oscilloscope
            self.draw_vertical_oscilloscope_cv(frame, cx, cy, color)
        elif self.window_kind == 15:   # Orbital pattern
            self.draw_orbital_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 16:   # Stacked bars with grid
            self.draw_stacked_bars_cv(frame, cx, cy, color)
    
    def draw_bar_chart_cv(self, frame, cx, cy, color):
        """繪製條形圖 - 與原始代碼相同"""
        for i in range(16):
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            bar_height = int(70 * noise_val)
            bar_x = int(cx - 70 + i * 9)
            bar_y = int(cy + 40)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 6, bar_y - bar_height), color, -1)
    
    def draw_line_chart_cv(self, frame, cx, cy, color):
        """繪製折線圖 - 與原始代碼相同"""
        points = []
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        # 畫15條連接線
        for i in range(15):
            cv2.line(frame, points[i], points[i+1], color, 1)
        
        # 畫16個點
        for px, py in points:
            cv2.circle(frame, (px, py), 2, color, -1)
    
    def draw_curve_chart_cv(self, frame, cx, cy, color):
        """繪製曲線圖 - 與原始代碼相同"""
        points = []
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        # 畫曲線
        for i in range(len(points) - 1):
            cv2.line(frame, points[i], points[i+1], color, 1)
        
        # 基準線
        cv2.line(frame, (int(cx - 67), int(cy + 8)), 
                 (int(cx + 77), int(cy + 8)), color, 1)
        
        # 垂直線
        for i in range(16):
            px, py = points[i]
            cv2.line(frame, (px, int(cy + 8)), (px, py), color, 1)
    
    def draw_matrix_display_cv(self, frame, cx, cy, color):
        """繪製矩陣顯示 - 與原始代碼相同"""
        for i in range(9):
            for j in range(3):
                noise_val = pde_noise(i, j, frame_count * CONTENT_ANIMATION_SPEED)
                text_val = int(noise_val * 10)
                body_val = int(noise_val * 20)
                px = int(cx - 62.5 + i * 15)
                py = int(cy - 25 + j * 20)
                self.draw_shaba_text_cv(frame, text_val, body_val, px, py, color)
    
    def draw_shaba_text_cv(self, frame, tag_point, tag_body, px, py, color):
        """繪製矩陣文字 - 與原始代碼相同"""
        # 畫點
        if tag_point == 1:
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, -1)
        elif tag_point == 2:
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, -1)
        elif tag_point == 3:
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, -1)
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, -1)
        
        # 畫主體
        tag_body = tag_body % 8
        if tag_body == 0:
            cv2.line(frame, (px + 1, py + 5), (px + 1, py + 11), color, 1)
            cv2.line(frame, (px + 1, py + 11), (px + 7, py + 11), color, 1)
            cv2.line(frame, (px + 7, py + 11), (px + 7, py + 5), color, 1)
        elif tag_body == 1:
            cv2.line(frame, (px + 1, py + 5), (px + 7, py + 5), color, 1)
            cv2.line(frame, (px + 1, py + 5), (px + 1, py + 11), color, 1)
            cv2.line(frame, (px + 1, py + 11), (px + 7, py + 11), color, 1)
        elif tag_body == 2:
            cv2.line(frame, (px + 1, py + 5), (px + 7, py + 5), color, 1)
            cv2.line(frame, (px + 1, py + 5), (px + 1, py + 11), color, 1)
            cv2.line(frame, (px + 7, py + 11), (px + 7, py + 5), color, 1)
        elif tag_body == 3:
            cv2.line(frame, (px + 1, py + 5), (px + 7, py + 5), color, 1)
            cv2.line(frame, (px + 1, py + 11), (px + 7, py + 11), color, 1)
            cv2.line(frame, (px + 7, py + 11), (px + 7, py + 5), color, 1)
        elif tag_body == 4:
            cv2.line(frame, (px + 1, py + 5), (px + 7, py + 5), color, 1)
            cv2.line(frame, (px + 1, py + 5), (px + 1, py + 11), color, 1)
        elif tag_body == 5:
            cv2.line(frame, (px + 1, py + 5), (px + 1, py + 11), color, 1)
            cv2.line(frame, (px + 1, py + 11), (px + 7, py + 11), color, 1)
        elif tag_body == 6:
            cv2.line(frame, (px + 1, py + 11), (px + 7, py + 11), color, 1)
            cv2.line(frame, (px + 7, py + 11), (px + 7, py + 5), color, 1)
        elif tag_body == 7:
            cv2.line(frame, (px + 1, py + 5), (px + 7, py + 5), color, 1)
            cv2.line(frame, (px + 7, py + 11), (px + 7, py + 5), color, 1)
    
    def draw_geometric_pattern_cv(self, frame, cx, cy, color):
        """繪製幾何圖案 - 與原始代碼相同"""
        for j in range(8):
            fill_noise = pde_noise(self.i + j, frame_count * CONTENT_ANIMATION_SPEED)
            if fill_noise > 0.5:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in color)
            else:
                fill_color = None
            
            # 根據原始代碼繪製不同的三角形
            if j == 0:  # 中心三角形
                points = np.array([
                    [cx, cy - 30], 
                    [cx - 20, cy + 30], 
                    [cx + 20, cy + 30]
                ], np.int32)
            elif j == 1:  # 右上
                points = np.array([
                    [cx + 10, cy - 3], 
                    [cx + 30, cy - 30], 
                    [cx + 65, cy - 30], 
                    [cx + 65, cy - 20]
                ], np.int32)
            elif j == 2:  # 右中
                points = np.array([
                    [cx + 10, cy + 5], 
                    [cx + 65, cy - 10], 
                    [cx + 65, cy + 10]
                ], np.int32)
            elif j == 3:  # 右下
                points = np.array([
                    [cx + 10, cy + 13], 
                    [cx + 65, cy + 20], 
                    [cx + 65, cy + 35], 
                    [cx + 30, cy + 35]
                ], np.int32)
            elif j == 4:  # 下
                points = np.array([
                    [cx, cy + 10], 
                    [cx + 20, cy + 35], 
                    [cx - 20, cy + 35]
                ], np.int32)
            elif j == 5:  # 左下
                points = np.array([
                    [cx - 10, cy + 13], 
                    [cx - 30, cy + 35], 
                    [cx - 65, cy + 35], 
                    [cx - 65, cy + 20]
                ], np.int32)
            elif j == 6:  # 左中
                points = np.array([
                    [cx - 10, cy + 5], 
                    [cx - 65, cy + 10], 
                    [cx - 65, cy - 10]
                ], np.int32)
            else:  # 左上
                points = np.array([
                    [cx - 10, cy - 3], 
                    [cx - 65, cy - 20], 
                    [cx - 65, cy - 30], 
                    [cx - 30, cy - 30]
                ], np.int32)
            
            if fill_color:
                cv2.fillPoly(frame, [points], fill_color)
            cv2.polylines(frame, [points], True, color, 1)
    
    def draw_grid_pattern_cv(self, frame, cx, cy, color):
        """繪製網格圖案 - 與原始代碼相同"""
        for i in range(16):
            for j in range(3):
                temp_value = pde_noise((j * 16 + i), frame_count * 0.01)
                px = int(cx - 64 + i * 8)
                py = int(cy - 30 + j * 23)
                cell_w = 8
                cell_h = 20
                
                if temp_value > 0.7:
                    fill_alpha = int(100 * self.alpha)
                    fill_color = tuple(int(c * fill_alpha / 255) for c in color)
                    cv2.rectangle(frame, (px, py), (px + cell_w, py + cell_h), fill_color, -1)
                elif temp_value > 0.6:
                    cv2.rectangle(frame, (px, py), (px + cell_w, py + cell_h), color, 1)
    
    def draw_oscilloscope_cv(self, frame, cx, cy, color):
        """繪製示波器 - 與原始代碼相同"""
        for i in range(4):
            temp_value = pde_noise(i + 2, frame_count * 0.01)
            line_y = int(cy - 15 + i * 15)
            cv2.line(frame, (int(cx - 64), line_y), (int(cx + 64), line_y), color, 1)
            
            # 動態點
            dot_x = int(cx - 64 + temp_value * 128)
            cv2.circle(frame, (dot_x, line_y), 2, color, -1)
    
    def draw_radar_pattern_cv(self, frame, cx, cy, color):
        """繪製雷達圖案 - 與原始代碼相同"""
        cv2.circle(frame, (cx, cy), 5, color, -1)
        cv2.line(frame, (int(cx - 64), cy), (int(cx + 64), cy), color, 1)
        
        for i in range(6):
            temp_value = pde_noise(i + 8, frame_count * 0.02)
            radius = 10 + i * 5
            start_angle = int(360 * temp_value)
            span_angle = 30 + i * 8
            
            # OpenCV的橢圓弧
            cv2.ellipse(frame, (cx, cy), (radius, radius), 0, start_angle, start_angle + span_angle, color, 1)
    
    def draw_complex_shapes_cv(self, frame, cx, cy, color):
        """繪製複雜形狀 - 與原始代碼相同"""
        cv2.circle(frame, (cx, cy), 5, color, -1)
        
        for i in range(6):
            temp_value = pde_noise(i * 1.5 + 9, frame_count * 0.03)
            rotation = 360 * temp_value
            
            fill_noise = pde_noise(i + 108, frame_count * 0.07)
            if fill_noise > 0.5:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
            else:
                fill_color = None
            
            # 繪製旋轉的多邊形
            points = []
            for j in range(i*2+8):
                angle_rad = math.radians(j * 7 + rotation)
                x1 = cx + i*2*3 * math.cos(angle_rad)
                y1 = cy + i*2*3 * math.sin(angle_rad)
                points.append([int(x1), int(y1)])
            
            for j in range(i*2+7, -1, -1):
                angle_rad = math.radians(j * 7 + rotation)
                x2 = cx + (i*2+1)*3 * math.cos(angle_rad)
                y2 = cy + (i*2+1)*3 * math.sin(angle_rad)
                points.append([int(x2), int(y2)])
            
            if points:
                points_array = np.array(points, np.int32)
                if fill_color:
                    cv2.fillPoly(frame, [points_array], fill_color)
                cv2.polylines(frame, [points_array], True, color, 1)
    
    def draw_crosshair_pattern_cv(self, frame, cx, cy, color):
        """繪製十字準星 - 與原始代碼相同"""
        temp_x1 = pde_noise(self.i + 110, frame_count * 0.013)
        temp_y1 = pde_noise(self.i + 111, frame_count * 0.012)
        temp_x2 = pde_noise(self.i + 112, frame_count * 0.014)
        temp_y2 = pde_noise(self.i + 113, frame_count * 0.015)
        
        # 第一組十字線
        line_y1 = int(cy + temp_y1 * 90 - 45)  # self.height * 0.9 - self.height * 0.45
        line_x1 = int(cx + temp_x1 * 160 - 80)  # self.width - self.width * 0.5
        cv2.line(frame, (int(cx - 72), line_y1), (int(cx + 72), line_y1), color, 1)  # -self.width * 0.45
        cv2.line(frame, (line_x1, int(cy - 35)), (line_x1, int(cy + 40)), color, 1)  # -self.height * 0.35, self.height * 0.4
        
        # 第一組標記
        mark_alpha = int(100 * self.alpha)
        mark_color = tuple(int(c * mark_alpha / 255) for c in (255, 255, 255))
        
        offsets = [(0.02, -0.03), (0.05, -0.03), (-0.02, -0.03), (-0.05, -0.03),
                   (0.02, 0.03), (0.05, 0.03), (-0.02, 0.03), (-0.05, 0.03)]
        
        for dx, dy in offsets:
            mark_x = int(cx - 80 + (temp_x1 + dx) * 160)  # -self.width * 0.5 + (temp_x1 + dx) * self.width
            mark_y = int(cy + (temp_y1 + dy) * 90 - 45)   # (temp_y1 + dy) * self.height * 0.9 - self.height * 0.45
            if abs(dx) > abs(dy):
                cv2.line(frame, (mark_x - 3, mark_y), (mark_x + 3, mark_y), mark_color, 1)
            else:
                cv2.line(frame, (mark_x, mark_y - 4), (mark_x, mark_y + 4), mark_color, 1)
        
        # 第二組十字線
        line_y2 = int(cy + temp_y2 * 90 - 45)
        line_x2 = int(cx + temp_x2 * 160 - 80)
        cv2.line(frame, (int(cx - 72), line_y2), (int(cx + 72), line_y2), color, 1)
        cv2.line(frame, (line_x2, int(cy - 35)), (line_x2, int(cy + 40)), color, 1)
    
    def draw_diamond_shapes_cv(self, frame, cx, cy, color):
        """繪製菱形 - 與原始代碼相同"""
        shapes = [
            # 中心鑽石
            [(0, -30), (16, 2.5), (0, 35), (-16, 2.5)],
            # 其他8個形狀
            [(16, -30), (32, -30), (48, -5), (32, -5)],
            [(16, 35), (32, 35), (48, 10), (32, 10)],
            [(-16, -30), (-32, -30), (-48, -5), (-32, -5)],
            [(-16, 35), (-32, 35), (-48, 10), (-32, 10)],
            [(48, -30), (64, -30), (64, -5)],
            [(48, 35), (64, 35), (64, 10)],
            [(-48, -30), (-64, -30), (-64, -5)],
            [(-48, 35), (-64, 35), (-64, 10)]
        ]
        
        for i, shape_points in enumerate(shapes):
            fill_noise = pde_noise(self.i + 111 + i, frame_count * 0.021)
            points = np.array([[cx + x, cy + y] for x, y in shape_points], np.int32)
            
            if fill_noise > 0.5:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
                cv2.fillPoly(frame, [points], fill_color)
            cv2.polylines(frame, [points], True, color, 1)
    
    def draw_level_indicators_cv(self, frame, cx, cy, color):
        """繪製等級指示器 - 與原始代碼相同"""
        temp_value = pde_noise(self.i + 13, frame_count * CONTENT_ANIMATION_SPEED) * 15 - 1
        
        # 垂直等級條
        for i in range(13):
            if i <= temp_value:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
                bar_y = int(cy + 35 - 5 * i)  # self.height * 0.35 - self.height * 0.05 * i
                bar_h = 5  # self.height * 0.05
                cv2.rectangle(frame, (int(cx - 8), bar_y - bar_h), 
                             (int(cx + 8), bar_y), fill_color, -1)  # -self.width * 0.05, self.width * 0.05
            else:
                bar_y = int(cy + 35 - 5 * i)
                bar_h = 5
                cv2.rectangle(frame, (int(cx - 8), bar_y - bar_h), 
                             (int(cx + 8), bar_y), color, 1)
        
        # 側邊標記點
        for i in range(0, 13, 2):
            mark_y = int(cy + 35 - 5 * i)
            cv2.circle(frame, (int(cx - 16), mark_y), 2, color, -1)  # -self.width * 0.1
            cv2.circle(frame, (int(cx + 16), mark_y), 2, color, -1)  # self.width * 0.1
    
    def draw_progress_bars_cv(self, frame, cx, cy, color):
        """繪製進度條 - 與原始代碼相同"""
        for i in range(4):
            temp_value = pde_noise(i + 1, frame_count * CONTENT_ANIMATION_SPEED)
            bar_y = int(cy - 25 + 15 * i)  # -self.height * (0.25 - 0.15 * i)
            bar_h = 10  # self.height * 0.1
            
            # 填充部分
            filled_width = int(temp_value * 128) - 2  # self.width * 0.8
            cv2.rectangle(frame, (int(cx - 64), bar_y), 
                         (int(cx - 64) + filled_width, bar_y + bar_h), color, -1)  # -self.width * 0.4
            
            # 空白部分
            empty_start = int(cx - 64) + filled_width + 3
            empty_width = 128 - filled_width - 3  # self.width * 0.8 - filled_width - 3
            cv2.rectangle(frame, (empty_start, bar_y), (empty_start + empty_width, bar_y + bar_h), color, 1)
    
    def draw_vertical_oscilloscope_cv(self, frame, cx, cy, color):
        """繪製垂直示波器 - 與原始代碼相同"""
        for i in range(16):
            bar_x = int(cx - 70 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            
            # 向上的線
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 - 35 * noise_val)), color, 1)
            # 向下的線
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 + 35 * noise_val)), color, 1)
    
    def draw_orbital_pattern_cv(self, frame, cx, cy, color):
        """繪製軌道圖案 - 與原始代碼相同"""
        temp_values = [
            pde_noise(self.i + 215, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 216, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 217, frame_count * CONTENT_ANIMATION_SPEED)
        ]
        
        center_x = int(cx - 24)  # -self.width * 0.15 for width=160
        center_y = int(cy + 5)   # self.height * 0.05 for height=100
        
        # 三個同心圓
        r1 = 8   # self.width * 0.05
        cv2.circle(frame, (center_x, center_y), r1, color, 1)
        r2 = 20  # self.width * 0.125
        cv2.circle(frame, (center_x, center_y), r2, color, 1)
        r3 = 32  # self.width * 0.2
        cv2.circle(frame, (center_x, center_y), r3, color, 1)
        
        # 基準點
        base_x = int(cx - 8)   # -self.width * 0.05
        base_y = int(cy + 5)   # self.height * 0.05
        
        # 軌道線和軌道點
        radii = [8, 20, 32]  # 對應原始代碼的寬度比例
        for i, (radius, temp_val) in enumerate(zip(radii, temp_values)):
            angle_rad = math.radians(temp_val * 360)
            orbit_x = int(radius * math.cos(angle_rad)) + center_x
            orbit_y = int(radius * math.sin(angle_rad)) + center_y
            
            # 連接線
            cv2.line(frame, (base_x, base_y), (orbit_x, orbit_y), color, 1)
            
            # 軌道點
            point_r = 4  # self.width * 0.025
            cv2.circle(frame, (orbit_x, orbit_y), point_r, color, 1)
    
    def draw_stacked_bars_cv(self, frame, cx, cy, color):
        """繪製堆疊條形圖 - 與原始代碼相同"""
        temp_values = [
            pde_noise(self.i + 215, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 216, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 217, frame_count * CONTENT_ANIMATION_SPEED)
        ]
        
        # 水平網格線
        for i in range(14):
            line_y = int(cy - 30 + i * 5)  # -self.height * (0.3 - i * 0.05)
            cv2.line(frame, (int(cx - 64), line_y), 
                     (int(cx + 64), line_y), color, 1)
        
        # 三個堆疊條
        fill_alpha = int(100 * self.alpha)
        fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
        
        # 左條
        bar_height = int(temp_values[0] * 90)  # self.height * 0.9
        cv2.rectangle(frame, (int(cx - 40), int(cy + 40)), 
                     (int(cx - 24), int(cy + 40) - bar_height), fill_color, -1)
        
        # 中條
        bar_height = int(temp_values[1] * 90)
        cv2.rectangle(frame, (int(cx - 8), int(cy + 40)), 
                     (int(cx + 8), int(cy + 40) - bar_height), fill_color, -1)
        
        # 右條
        bar_height = int(temp_values[2] * 90)
        cv2.rectangle(frame, (int(cx + 24), int(cy + 40)), 
                     (int(cx + 40), int(cy + 40) - bar_height), fill_color, -1)

class ImprovedDetectionWindowEffect:
    """改進的檢測窗口效果 - 參考原始 cal_windows.py"""
    
    def __init__(self, screen_width=1080, screen_height=1920):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.windows_by_face = {}
        self.center_points_by_face = {}  # 每個人臉的中心點
        self.spawn_rate = 0.1  # 原始 SPAWN_RATE
        
        # 新增：窗口顯示控制
        self.face_states = {}  # 記錄每個人臉的檢測框狀態
        self.window_spawn_delays = {}  # 記錄窗口生成延遲
        self.max_windows_per_face = 4  # 每個人臉最多4個窗口
        self.spawn_delay_frames = 30  # 狀態3後延遲30幀再開始生成窗口
        
    def update_faces(self, faces, face_states=None):
        """更新人臉檢測結果"""
        current_face_ids = set(range(len(faces)))
        
        # 清理不存在的人臉
        for face_id in list(self.windows_by_face.keys()):
            if face_id not in current_face_ids:
                del self.windows_by_face[face_id]
                if face_id in self.center_points_by_face:
                    del self.center_points_by_face[face_id]
                if face_id in self.face_states:
                    del self.face_states[face_id]
                if face_id in self.window_spawn_delays:
                    del self.window_spawn_delays[face_id]
        
        # 更新人臉狀態
        if face_states:
            for face_id, state in face_states.items():
                if face_id in current_face_ids:
                    self.face_states[face_id] = state
                    
                    # 當狀態變為3時，開始延遲計時
                    if state == 3 and face_id not in self.window_spawn_delays:
                        self.window_spawn_delays[face_id] = 0
        
        # 為每個人臉更新窗口
        for i, (x, y, w, h) in enumerate(faces):
            center_x = x + w // 2
            center_y = y + h // 2
            face_size = max(w, h)
            
            if i not in self.windows_by_face:
                self.windows_by_face[i] = []
                # 為新人臉生成4個隨機中心點
                self.generate_center_points_for_face(i, center_x, center_y, face_size)
            
            # 更新現有窗口的中心點（讓窗口跟隨檢測框）
            for window in self.windows_by_face[i]:
                window.update_center(center_x, center_y)
            
            # 更新生成點位置（讓生成點跟隨檢測框移動，但保持穩定）
            if i in self.center_points_by_face and self.center_points_by_face[i]:
                # 只在檢測框移動超過一定距離時才更新（減少計算）
                old_center_x = self.center_points_by_face[i][0][0] if self.center_points_by_face[i] else center_x
                old_center_y = self.center_points_by_face[i][0][1] if self.center_points_by_face[i] else center_y
                offset_x = center_x - old_center_x
                offset_y = center_y - old_center_y
                
                # 只有當移動距離超過閾值時才更新
                if abs(offset_x) > 2 or abs(offset_y) > 2:
                    # 更新所有生成點的位置（保持相對位置不變）
                    updated_points = []
                    for point in self.center_points_by_face[i]:
                        new_x = point[0] + offset_x
                        new_y = point[1] + offset_y
                        # 確保點在屏幕範圍內
                        new_x = max(100, min(1080 - 100, new_x))
                        new_y = max(100, min(1920 - 100, new_y))
                        updated_points.append((int(new_x), int(new_y)))
                    
                    self.center_points_by_face[i] = updated_points
                    
                    # 更新現有窗口的生成點位置
                    for window in self.windows_by_face[i]:
                        if hasattr(window, 'spawn_center_x') and hasattr(window, 'spawn_center_y'):
                            # 更新窗口的生成點位置
                            window.spawn_center_x += offset_x
                            window.spawn_center_y += offset_y
            
            # 檢查是否可以生成新窗口
            can_spawn = self._can_spawn_window(i)
            
            # 生成新窗口 - 一個一個顯示
            if can_spawn and len(self.windows_by_face[i]) < self.max_windows_per_face:
                if i in self.center_points_by_face and self.center_points_by_face[i]:
                    # 從隨機中心點生成窗口，但確保每個窗口使用不同的生成點
                    available_spawn_points = self.center_points_by_face[i].copy()
                    
                    # 移除已經被使用的生成點
                    for window in self.windows_by_face[i]:
                        if hasattr(window, 'spawn_center_x') and hasattr(window, 'spawn_center_y'):
                            for point in available_spawn_points[:]:
                                if abs(point[0] - window.spawn_center_x) < 10 and abs(point[1] - window.spawn_center_y) < 10:
                                    available_spawn_points.remove(point)
                                    break
                    
                    # 如果有可用的生成點，創建新窗口
                    if available_spawn_points:
                        # 取出這次要連線的 point
                        spawn_center = random.choice(available_spawn_points)
                        # window 位置在同一個 corner 隨機產生，但不等於 point
                        corner_index = self.center_points_by_face[i].index(spawn_center)
                        win_x, win_y = self._random_corner_position(center_x, center_y, face_size, corner_index)
                        new_window = ImprovedCalWindow(win_x, win_y, face_size)
                        # 讓 window 連線目標指向 spawn_center
                        new_window.spawn_center_x = spawn_center[0]
                        new_window.spawn_center_y = spawn_center[1]
                        # 確保 window 的生成點位置正確設置
                        new_window.update_position()
                        # 調試：檢查連接線設置
                        print(f"Window {len(self.windows_by_face[i])} 連線到點: ({spawn_center[0]}, {spawn_center[1]})")
                        self.windows_by_face[i].append(new_window)
                        
                        # 重置延遲計時器，為下一個窗口做準備
                        if i in self.window_spawn_delays:
                            self.window_spawn_delays[i] = 0
                            # 增加額外延遲，讓窗口一個一個顯示
                            self.window_spawn_delays[i] = -60  # 負值表示額外延遲
                        
                        # 重置延遲計時器，為下一個窗口做準備
                        if i in self.window_spawn_delays:
                            self.window_spawn_delays[i] = 0
                            # 增加額外延遲，讓窗口一個一個顯示
                            self.window_spawn_delays[i] = -60  # 負值表示額外延遲
            
            # 更新現有窗口並移除已死亡的
            self.windows_by_face[i] = [w for w in self.windows_by_face[i] if w.update()]
    
    def _can_spawn_window(self, face_id):
        """檢查是否可以生成新窗口"""
        # 檢查人臉狀態是否為3或更高
        if face_id not in self.face_states:
            return False
            
        current_state = self.face_states[face_id]
        if current_state < 3:
            return False
        
        # 檢查延遲計時器
        if face_id not in self.window_spawn_delays:
            return False
            
        # 如果延遲計時器還沒到，增加計數
        if self.window_spawn_delays[face_id] < self.spawn_delay_frames:
            self.window_spawn_delays[face_id] += 1
            return False
        
        # 處理負值延遲（額外延遲）
        if self.window_spawn_delays[face_id] < 0:
            self.window_spawn_delays[face_id] += 1
            return False
        
        # 檢查生成概率 - 降低生成率，讓窗口一個一個顯示
        spawn_chance = self.spawn_rate * 0.3  # 降低生成概率
        return random.random() < spawn_chance
    
    def generate_center_points_for_face(self, face_id, center_x, center_y, face_size):
        """為人臉生成4個隨機中心點 - 分佈在檢測框的四個角落區域，避開中心30x30區域"""
        center_points = []
        
        # 計算檢測框的邊界
        frame_half_size = face_size * 0.65  # 檢測框的一半大小
        frame_left = center_x - frame_half_size
        frame_right = center_x + frame_half_size
        frame_top = center_y - frame_half_size
        frame_bottom = center_y + frame_half_size
        
        # 定義中心30x30避開區域
        center_avoid_left = center_x - 15
        center_avoid_right = center_x + 15
        center_avoid_top = center_y - 15
        center_avoid_bottom = center_y + 15
        
        # 定義四個角落區域的範圍（在檢測框內部，但避開中心區域）
        corner_regions = [
            # 左上角區域
            (frame_left + 20, frame_top + 20, center_avoid_left - 10, center_avoid_top - 10),
            # 右上角區域
            (center_avoid_right + 10, frame_top + 20, frame_right - 20, center_avoid_top - 10),
            # 右下角區域
            (center_avoid_right + 10, center_avoid_bottom + 10, frame_right - 20, frame_bottom - 20),
            # 左下角區域
            (frame_left + 20, center_avoid_bottom + 10, center_avoid_left - 10, frame_bottom - 20)
        ]
        
        for i, (x1, y1, x2, y2) in enumerate(corner_regions):
            # 確保區域有效（x1 < x2 且 y1 < y2）
            if x1 >= x2 or y1 >= y2:
                # 如果區域無效，使用備用區域
                if i == 0:  # 左上
                    x1, y1, x2, y2 = frame_left + 20, frame_top + 20, center_x - 25, center_y - 25
                elif i == 1:  # 右上
                    x1, y1, x2, y2 = center_x + 25, frame_top + 20, frame_right - 20, center_y - 25
                elif i == 2:  # 右下
                    x1, y1, x2, y2 = center_x + 25, center_y + 25, frame_right - 20, frame_bottom - 20
                else:  # 左下
                    x1, y1, x2, y2 = frame_left + 20, center_y + 25, center_x - 25, frame_bottom - 20
            
            # 在每個角落區域內隨機生成點
            x = random.randint(int(x1), int(x2))
            y = random.randint(int(y1), int(y2))
            
            # 確保點在屏幕範圍內
            x = max(100, min(1080 - 100, x))
            y = max(100, min(1920 - 100, y))
            
            center_points.append((int(x), int(y)))
            # 調試：顯示每個點的生成位置
            print(f"生成點 {i}: ({int(x)}, {int(y)}) - 角落: {['左上', '右上', '右下', '左下'][i]}")
        
        self.center_points_by_face[face_id] = center_points
    
    def set_flicker_state_for_face(self, face_id, should_flicker):
        """設置閃爍狀態"""
        if face_id in self.windows_by_face:
            for window in self.windows_by_face[face_id]:
                window.set_force_flicker(should_flicker)
    
    def draw_all_windows(self, frame, color_bgr=(255, 255, 255)):
        """繪製所有窗口"""
        # 調試：顯示生成點
        self._draw_debug_spawn_points(frame)
        
        for windows in self.windows_by_face.values():
            for window in windows:
                window.draw_on_cv_frame(frame, color_bgr)
    
    def _draw_debug_spawn_points(self, frame):
        """調試：繪製生成點"""
        # 移除調試繪製以提高性能
        pass
    
    def get_total_window_count(self):
        """獲取總窗口數量"""
        return sum(len(windows) for windows in self.windows_by_face.values())
    
    def clear_all_windows(self):
        """清空所有窗口"""
        self.windows_by_face.clear()
    
    def _random_corner_position(self, center_x, center_y, face_size, corner_index):
        """根據 corner_index 在四角隨機產生一個位置，避開中心30x30區域"""
        frame_half_size = face_size * 0.65
        frame_left = center_x - frame_half_size
        frame_right = center_x + frame_half_size
        frame_top = center_y - frame_half_size
        frame_bottom = center_y + frame_half_size
        
        # 定義中心30x30避開區域
        center_avoid_left = center_x - 15
        center_avoid_right = center_x + 15
        center_avoid_top = center_y - 15
        center_avoid_bottom = center_y + 15
        
        # 定義四個角落區域的範圍（在檢測框內部，但避開中心區域）
        corner_regions = [
            # 左上角區域
            (frame_left + 20, frame_top + 20, center_avoid_left - 10, center_avoid_top - 10),
            # 右上角區域
            (center_avoid_right + 10, frame_top + 20, frame_right - 20, center_avoid_top - 10),
            # 右下角區域
            (center_avoid_right + 10, center_avoid_bottom + 10, frame_right - 20, frame_bottom - 20),
            # 左下角區域
            (frame_left + 20, center_avoid_bottom + 10, center_avoid_left - 10, frame_bottom - 20)
        ]
        
        x1, y1, x2, y2 = corner_regions[corner_index]
        
        # 確保區域有效（x1 < x2 且 y1 < y2）
        if x1 >= x2 or y1 >= y2:
            # 如果區域無效，使用備用區域
            if corner_index == 0:  # 左上
                x1, y1, x2, y2 = frame_left + 20, frame_top + 20, center_x - 25, center_y - 25
            elif corner_index == 1:  # 右上
                x1, y1, x2, y2 = center_x + 25, frame_top + 20, frame_right - 20, center_y - 25
            elif corner_index == 2:  # 右下
                x1, y1, x2, y2 = center_x + 25, center_y + 25, frame_right - 20, frame_bottom - 20
            else:  # 左下
                x1, y1, x2, y2 = frame_left + 20, center_y + 25, center_x - 25, frame_bottom - 20
        
        x = random.randint(int(x1), int(x2))
        y = random.randint(int(y1), int(y2))
        x = max(100, min(1080 - 100, x))
        y = max(100, min(1920 - 100, y))
        return int(x), int(y)

# 創建簡化的檢測覆蓋層類
class DebugDetectionOverlay:
    """簡化的檢測覆蓋層 - 使用主程序的配置和效果"""
    
    def __init__(self):
        # 載入與主程序相同的動畫配置
        self.anim_config = AnimConfigLoader()
        
        # 驗證配置
        config_errors = self.anim_config.validate_config()
        if config_errors:
            print("🔧 動畫配置警告:")
            for key, error in config_errors.items():
                print(f"  {error}")
        
        # 檢測框列表
        self.visual_rects = []
        
        # 科技感窗口效果管理器 (使用改進的邏輯)
        self.window_effect = ImprovedDetectionWindowEffect(screen_width=1080, screen_height=1920)
        
        print("✅ 使用主程序的動畫配置和Cal Windows效果")
    
    def update_visual_rects_main_loop(self, faces):
        """更新視覺矩形 - 主循環調用"""
        # 調整視覺矩形數量
        while len(self.visual_rects) > len(faces):
            self.visual_rects.pop()
        
        while len(self.visual_rects) < len(faces):
            if len(faces) > len(self.visual_rects):
                x, y, w, h = faces[len(self.visual_rects)]
                center_x = x + w // 2
                center_y = y + h // 2
                rect = VisualRect(center_x, center_y, w, h, self.anim_config)
                self.visual_rects.append(rect)
        
        # 更新現有矩形並收集狀態
        face_states = {}
        for i, (x, y, w, h) in enumerate(faces):
            if i < len(self.visual_rects):
                center_x = x + w // 2
                center_y = y + h // 2
                self.visual_rects[i].update(center_x, center_y, w, h)
                
                # 收集檢測框狀態
                face_states[i] = self.visual_rects[i].state
        
        # 更新科技窗口，傳遞狀態信息
        self.window_effect.update_faces(faces, face_states)
        
        # 同步閃爍狀態和檢測框狀態
        for i, rect in enumerate(self.visual_rects):
            if hasattr(rect, 'is_flickering'):
                self.window_effect.set_flicker_state_for_face(i, rect.is_flickering)
            # 同步檢測框狀態到窗口
            if i in self.window_effect.windows_by_face:
                for window in self.window_effect.windows_by_face[i]:
                    window.set_detection_state(rect.state)
    
    def draw_on_frame(self, frame):
        """在幀上繪製檢測框和效果"""
        # 繪製檢測框動畫
        for rect in self.visual_rects:
            rect.draw(frame)
        
        # 繪製科技窗口
        self.window_effect.draw_all_windows(frame)
        
        return frame
    
    def clear_all_effects(self):
        """清空所有效果"""
        self.visual_rects.clear()
        self.window_effect.clear_all_windows()
    
    def reload_config(self):
        """重新載入配置"""
        self.anim_config.reload_config()
        print("🔄 動畫配置已重新載入")
    
    def get_animation_info(self):
        """獲取動畫信息"""
        info = {
            'rect_count': len(self.visual_rects),
            'window_count': self.window_effect.get_total_window_count(),
            'current_state': self.visual_rects[0].state if self.visual_rects else 0,
            'is_flickering': self.visual_rects[0].is_flickering if self.visual_rects else False
        }
        return info
        

# 真實人臉檢測器 (如果需要)
try:
    import mediapipe as mp
    mp_face_detection = mp.solutions.face_detection
    MEDIAPIPE_AVAILABLE = True
    print("✅ MediaPipe 已載入，支援真實人臉檢測")
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False
    print("⚠️ MediaPipe 未安裝，僅支援模擬人臉")

class RealFaceDetector:
    """真實人臉檢測器 - 與主程序相同邏輯"""
    
    def __init__(self):
        self.face_detection = None
        
        if MEDIAPIPE_AVAILABLE:
            try:
                config = {
                    'detection_sensitivity': 0.95,
                    'tracking_smoothing': 0.4,
                    'min_face_area_ratio': 0.001
                }
                
                self.face_detection = mp_face_detection.FaceDetection(
                    model_selection=1,
                    min_detection_confidence=config['detection_sensitivity']
                )
                
                self.smoothing_factor = config['tracking_smoothing']
                self.min_face_area_ratio = config['min_face_area_ratio']
                self.last_detection = None
                self.use_low_res_detection = True
                
                print("🎯 真實人臉檢測器初始化成功")
            except Exception as e:
                print(f"❌ 人臉檢測器初始化失敗: {e}")
                self.face_detection = None
    
    def process_frame(self, frame):
        """處理畫面並偵測人臉"""
        if frame is None or self.face_detection is None:
            return None
        
        if not hasattr(frame, 'shape') or len(frame.shape) < 2:
            return None
            
        try:
            detection_frame = frame
            scale_factor = 1.0
            
            if self.use_low_res_detection:
                detection_frame = self._prepare_detection_frame(frame)
                scale_factor = min(frame.shape[1] / detection_frame.shape[1], 
                                 frame.shape[0] / detection_frame.shape[0])
            
            rgb_frame = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
            results = self.face_detection.process(rgb_frame)
            
            if results and hasattr(results, 'detections') and results.detections:
                best_detection = self._select_main_face(results.detections, detection_frame.shape)
                
                if best_detection:
                    bbox = self._get_bbox_coords(best_detection, detection_frame.shape)
                    
                    if bbox:
                        if self.use_low_res_detection and scale_factor > 1.0:
                            bbox = self._scale_bbox_to_original(bbox, scale_factor)
                        
                        if self._is_face_size_valid(bbox, frame.shape):
                            smoothed_bbox = self._smooth_tracking(bbox)
                            self.last_detection = smoothed_bbox
                            return smoothed_bbox
            
            self.last_detection = None
            return None
            
        except Exception as e:
            print(f"人臉檢測錯誤: {e}")
            return None
    
    def _prepare_detection_frame(self, frame):
        height, width = frame.shape[:2]
        target_width = 640
        target_height = 360
        
        if width > target_width or height > target_height:
            scale = min(target_width / width, target_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        return frame
    
    def _select_main_face(self, detections, frame_shape):
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
            except Exception:
                continue
                
        return best_detection
    
    def _get_bbox_coords(self, detection, frame_shape):
        try:
            h, w = frame_shape[:2]
            
            if not hasattr(detection, 'location_data') or not detection.location_data:
                return None
                
            bbox = detection.location_data.relative_bounding_box
            if not bbox:
                return None
            
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)
            
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            width = min(width, w - x)
            height = min(height, h - y)
            
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
            print(f"錯誤取得bbox座標: {e}")
            return None
    
    def _smooth_tracking(self, new_bbox):
        if not self.last_detection:
            return new_bbox
        
        alpha = 1.0 - self.smoothing_factor
        
        smoothed_bbox = {
            'x': int(self.last_detection['x'] * self.smoothing_factor + new_bbox['x'] * alpha),
            'y': int(self.last_detection['y'] * self.smoothing_factor + new_bbox['y'] * alpha),
            'width': int(self.last_detection['width'] * self.smoothing_factor + new_bbox['width'] * alpha),
            'height': int(self.last_detection['height'] * self.smoothing_factor + new_bbox['height'] * alpha),
            'confidence': new_bbox['confidence']
        }
        
        return smoothed_bbox
    
    def _scale_bbox_to_original(self, bbox, scale_factor):
        return {
            'x': int(bbox['x'] * scale_factor),
            'y': int(bbox['y'] * scale_factor),
            'width': int(bbox['width'] * scale_factor),
            'height': int(bbox['height'] * scale_factor),
            'confidence': bbox['confidence']
        }
    
    def _is_face_size_valid(self, bbox, frame_shape):
        if not bbox:
            return False
            
        frame_area = frame_shape[0] * frame_shape[1]
        face_area = bbox['width'] * bbox['height']
        face_area_ratio = face_area / frame_area
        
        return face_area_ratio >= self.min_face_area_ratio

# ===== 攝像頭處理器 =====
class CameraProcessor(QThread):
    """攝像頭處理器 - 使用主程序的組件"""
    
    frame_ready = pyqtSignal(np.ndarray, list)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.use_camera = False
        self.camera = None
        self.frame_count = 0
        
        # 真實人臉檢測器
        self.face_detector = RealFaceDetector()
        
        # 模擬人臉數據
        self.simulate_faces = False
        self.face_positions = []
        self.init_face_movement()
        
        # 使用簡化的DetectionOverlay (包含主程序的配置和效果)
        self.detection_overlay = DebugDetectionOverlay()
        
        # 啟動時嘗試開啟攝像頭
        self.try_enable_camera()
        
    def init_face_movement(self):
        """初始化人臉移動參數"""
        self.face_center_x = 540
        self.face_center_y = 960
        self.face_velocity_x = random.uniform(-2, 2)
        self.face_velocity_y = random.uniform(-2, 2)
        
    def try_enable_camera(self):
        """嘗試啟用攝像頭"""
        try:
            test_camera = cv2.VideoCapture(0)
            if test_camera.isOpened():
                ret, _ = test_camera.read()
                if ret:
                    self.camera = test_camera
                    self.use_camera = True
                    print("🎥 攝像頭自動啟用成功")
                else:
                    test_camera.release()
                    print("📹 攝像頭無法讀取畫面，使用模擬模式")
            else:
                test_camera.release()
                print("📹 攝像頭不可用，使用模擬模式")
        except Exception as e:
            print(f"📹 攝像頭初始化失敗: {e}，使用模擬模式")
    
    def generate_moving_face(self):
        """生成移動的人臉位置"""
        self.face_center_x += self.face_velocity_x
        self.face_center_y += self.face_velocity_y
        
        if self.face_center_x < 200 or self.face_center_x > 880:
            self.face_velocity_x *= -1
        if self.face_center_y < 300 or self.face_center_y > 1600:
            self.face_velocity_y *= -1
            
        self.face_center_x = max(200, min(880, self.face_center_x))
        self.face_center_y = max(300, min(1600, self.face_center_y))
        
        size = 150
        x = int(self.face_center_x - size/2)
        y = int(self.face_center_y - size/2)
        self.face_positions = [(x, y, size, size)]
    

    def toggle_camera(self):
        """切換攝像頭/模擬模式"""
        if self.use_camera:
            if self.camera:
                self.camera.release()
                self.camera = None
            self.use_camera = False
            print("切換到模擬模式")
        else:
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                self.use_camera = True
                print("切換到攝像頭模式")
            else:
                print("無法開啟攝像頭，保持模擬模式")
                self.camera = None
    
    def toggle_face_simulation(self):
        """切換人臉模擬"""
        self.simulate_faces = not self.simulate_faces
        if self.simulate_faces:
            self.init_face_movement()
            print("人臉模擬: 開啟")
        else:
            self.detection_overlay.clear_all_effects()
            print("人臉模擬: 關閉 (使用真實人臉檢測)")
    
    def run(self):
        self.running = True
        
        while self.running:
            if self.use_camera and self.camera and self.camera.isOpened():
                ret, raw_frame = self.camera.read()
                if ret:
                    frame = self.process_camera_frame(raw_frame)
                    
                    if self.simulate_faces:
                        faces = self.face_positions
                    else:
                        faces = self.detect_real_faces(raw_frame)
                else:
                    frame = self.generate_test_frame()
                    faces = self.face_positions if self.simulate_faces else []
            else:
                frame = self.generate_test_frame()
                faces = self.face_positions if self.simulate_faces else []
            
            # 使用主程序的DetectionOverlay更新和繪製
            self.detection_overlay.update_visual_rects_main_loop(faces)
            
            # 繪製檢測框和科技窗口
            final_frame = self.detection_overlay.draw_on_frame(frame)
            
            self.frame_ready.emit(final_frame, faces)
            
            if self.simulate_faces:
                self.generate_moving_face()
            
            # 更新全域frame_count用於窗口動畫
            self.frame_count += 1
            global frame_count
            frame_count += 1
            self.msleep(16)  # ~60 FPS
    
    def process_camera_frame(self, raw_frame):
        """處理攝像頭畫面 - 使用與主程序相同的邏輯"""
        height, width = raw_frame.shape[:2]
        
        if width == 1080 and height == 1920:
            return raw_frame
        
        if width != 1920 or height != 1080:
            raw_frame = cv2.resize(raw_frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        # 使用正確的比例 (與主程序相同)
        target_crop_width = 607
        crop_x = 656
        crop_y = 0
        
        cropped_frame = raw_frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
    
    def generate_test_frame(self):
        """生成測試畫面"""
        raw_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        for y in range(1080):
            intensity = int(50 + 30 * np.sin(y * 0.005 + self.frame_count * 0.02))
            raw_frame[y, :] = [intensity//3, intensity//2, intensity]
        
        for i in range(0, 1920, 100):
            cv2.line(raw_frame, (i, 0), (i, 1080), (60, 60, 60), 1)
        for i in range(0, 1080, 100):
            cv2.line(raw_frame, (0, i), (1920, i), (60, 60, 60), 1)
        
        return self.process_camera_frame(raw_frame)
    
    def detect_real_faces(self, raw_frame):
        """使用真實人臉檢測器檢測人臉"""
        detection_result = self.face_detector.process_frame(raw_frame)
        
        if detection_result:
            adjusted_bbox = self.adjust_detection_coordinates(detection_result, raw_frame.shape)
            if adjusted_bbox:
                frame_offset_y = int(adjusted_bbox['height'] * 0.2)
                adjusted_y = int(adjusted_bbox['y']) - frame_offset_y
                adjusted_y = max(0, adjusted_y)
                
                face_rect = (int(adjusted_bbox['x']), adjusted_y, 
                           int(adjusted_bbox['width']), int(adjusted_bbox['height']))
                return [face_rect]
        
        return []
    
    def adjust_detection_coordinates(self, detection_result, original_shape):
        """調整檢測結果座標 - 與主程序相同邏輯"""
        if not detection_result:
            return None
            
        target_crop_width = 607
        crop_x_offset = 656
        
        face_left = detection_result['x']
        face_right = detection_result['x'] + detection_result['width']
        
        if face_right < crop_x_offset or face_left > crop_x_offset + target_crop_width:
            return None
        
        adjusted_x = max(0, detection_result['x'] - crop_x_offset)
        adjusted_width = min(detection_result['width'], target_crop_width - adjusted_x)
        adjusted_y = detection_result['y']
        adjusted_height = detection_result['height']
        
        scale_y = 1920.0 / 1080.0
        final_y = adjusted_y * scale_y
        final_height = adjusted_height * scale_y
        
        final_scale_x = 1080.0 / target_crop_width
        final_scale_y = 1920.0 / 1920.0
        
        final_result = {
            'x': adjusted_x * final_scale_x,
            'y': final_y * final_scale_y,
            'width': adjusted_width * final_scale_x,
            'height': final_height * final_scale_y,
            'confidence': detection_result.get('confidence', 0)
        }
        
        return final_result
    
    def stop(self):
        self.running = False
        if self.camera:
            self.camera.release()

# ===== 主調試窗口 =====
class CalWindowsDebugWindow(QMainWindow):
    """Cal Windows 效果調試窗口 - 使用主程序組件"""
    
    def __init__(self):
        super().__init__()
        self.setupUI()
        self.setupCamera()
        
    def setupUI(self):
        """設置UI"""
        self.setWindowTitle("Cal Windows Debug Tool - Using Main Program Components")
        
        # 使用與main.py相同的窗口尺寸
        self.window_width = 1080
        self.window_height = 1920
        self.setFixedSize(self.window_width, self.window_height)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(self.window_width, self.window_height)
        self.camera_label.setStyleSheet("background-color: black;")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.camera_label)
        central_widget.setLayout(layout)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: black;
            }
            QLabel {
                color: white;
                font-family: 'Arial', monospace;
            }
        """)
        
    def setupCamera(self):
        """設置攝像頭處理器"""
        self.camera_processor = CameraProcessor()
        self.camera_processor.frame_ready.connect(self.update_frame)
        self.camera_processor.start()
        
        print("🔧 Cal Windows 調試工具已初始化")
        print(f"📊 窗口尺寸: {self.window_width}x{self.window_height} (與main.py相同)")
        print("🎯 功能特色:")
        print("  ✅ 使用主程序的 DetectionOverlay")
        print("  ✅ 使用主程序的 AnimConfigLoader") 
        print("  ✅ 使用主程序的 DetectionWindowEffect")
        print("  ✅ 完全相同的動畫配置和效果")
        print("  ✅ 適合調試 Cal Windows 效果")
        
        if MEDIAPIPE_AVAILABLE:
            print("  🎯 人臉檢測: MediaPipe 可用")
        else:
            print("  ⚠️ 人臉檢測: MediaPipe 不可用，僅支援模擬")
        
        print("\n🎮 控制鍵:")
        print("  Space  - 切換真實/模擬人臉檢測")
        print("  C      - 切換攝像頭/模擬模式")
        print("  R      - 重新載入動畫配置")
        print("  Q/ESC  - 退出")
        
    def update_frame(self, frame, faces):
        """更新畫面"""
        try:
            # 轉換為Qt格式並顯示（移除調試信息）
            self.display_frame(frame)
            
        except Exception as e:
            print(f"更新畫面時發生錯誤: {e}")
    
    def draw_debug_info(self, frame, faces):
        """繪製調試信息"""
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, timestamp, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
        
        cv2.putText(frame, "CAL WINDOWS DEBUG TOOL", (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
        
        cv2.putText(frame, "Using Main Program Components", (20, 140), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 動畫信息
        animation_info = self.camera_processor.detection_overlay.get_animation_info()
        if animation_info:
            y_offset = 180
            cv2.putText(frame, f"Detection Rects: {animation_info['rect_count']}", (20, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            cv2.putText(frame, f"Cal Windows: {animation_info['window_count']}", (20, y_offset + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            
            if animation_info['rect_count'] > 0:
                cv2.putText(frame, f"Animation State: {animation_info['current_state']}", (20, y_offset + 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                cv2.putText(frame, f"Flickering: {'YES' if animation_info['is_flickering'] else 'NO'}", (20, y_offset + 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        
        # 模式狀態
        mode_text = "Camera Mode" if self.camera_processor.use_camera else "Simulation Mode"
        cv2.putText(frame, mode_text, (20, 350), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # 人臉檢測模式
        if self.camera_processor.simulate_faces:
            face_mode_text = f"Face Mode: SIMULATED ({len(faces)})"
            face_color = (0, 255, 255)
        else:
            if MEDIAPIPE_AVAILABLE:
                face_mode_text = f"Face Mode: REAL DETECTION ({len(faces)})"
                face_color = (0, 255, 0)
            else:
                face_mode_text = f"Face Mode: NO MEDIAPIPE ({len(faces)})"
                face_color = (0, 0, 255)
        
        cv2.putText(frame, face_mode_text, (20, 390), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, face_color, 2)
        
        # 控制提示
        controls = [
            "SPACE: Toggle Face Simulation",
            "C: Toggle Camera Mode", 
            "R: Reload Animation Config",
            "Q/ESC: Quit"
        ]
        
        y_offset = frame.shape[0] - 150
        for i, control in enumerate(controls):
                    cv2.putText(frame, control, (20, y_offset + i*30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    def display_frame(self, frame):
        """顯示畫面"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        self.camera_label.setPixmap(pixmap)
    
    def keyPressEvent(self, event):
        """鍵盤事件處理"""
        key = event.key()
        
        if key == Qt.Key.Key_Space:
            self.camera_processor.toggle_face_simulation()
            
        elif key == Qt.Key.Key_C:
            self.camera_processor.toggle_camera()
            
        elif key == Qt.Key.Key_R:
            # 重新載入動畫配置
            self.camera_processor.detection_overlay.reload_config()
            print("🔄 動畫配置已重新載入")
            
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
        
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """關閉事件"""
        print("正在關閉 Cal Windows 調試工具...")
        self.camera_processor.stop()
        self.camera_processor.wait()
        event.accept()

# ===== 主函數 =====
def main():
    """主函數"""
    print("🚀 Cal Windows 調試工具 (使用主程序組件)")
    print("=" * 60)
    print("📐 使用與主程序完全相同的組件:")
    print("  🎯 DetectionOverlay - 檢測框動畫系統")
    print("  🪟 DetectionWindowEffect - Cal Windows 效果")
    print("  📐 AnimConfigLoader - 動畫配置載入器")
    print("  🎛️ config/anim_config.csv - 實際配置文件")
    print("🎯 專為調試 Cal Windows 效果設計")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    debug_window = CalWindowsDebugWindow()
    debug_window.show()
    
    print("✅ Cal Windows 調試工具已啟動")
    print("📱 窗口尺寸: 1080x1920 (與main.py相同)")
    print("🎯 現在可以調試與主程序完全相同的 Cal Windows 效果！")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 