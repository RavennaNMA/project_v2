# Location: project_v2/debug_detection_complete_improved.py
# Usage: 調試工具 - 改進的點和窗口生成邏輯

import sys
import cv2
import numpy as np
import time
import random
import math
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

# 導入主程序的實際組件
import os
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.anim_config_loader import AnimConfigLoader

# 全域frame_count變數
frame_count = 0
CONTENT_ANIMATION_SPEED = 0.001

# Processing風格噪聲
class ProcessingStyleNoise:
    def __init__(self):
        self.noise_table = {}
        self.random_seed = random.randint(0, 10000)
        
    def noise(self, x, y=0, z=0):
        grid_size = 0.5
        x_grid = int(x / grid_size)
        y_grid = int(y / grid_size) 
        z_grid = int(z / grid_size)
        
        x_fract = (x / grid_size) - x_grid
        y_fract = (y / grid_size) - y_grid
        z_fract = (z / grid_size) - z_grid
        
        def grid_random(gx, gy, gz):
            seed = (gx * 73856093) ^ (gy * 19349663) ^ (gz * 83492791) ^ self.random_seed
            a = 1664525
            c = 1013904223
            m = 2**32
            return ((a * seed + c) % m) / m
        
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
        
        v00 = v000 * (1 - x_fract) + v100 * x_fract
        v01 = v001 * (1 - x_fract) + v101 * x_fract
        v10 = v010 * (1 - x_fract) + v110 * x_fract
        v11 = v011 * (1 - x_fract) + v111 * x_fract
        
        v0 = v00 * (1 - y_fract) + v10 * y_fract
        v1 = v01 * (1 - y_fract) + v11 * y_fract
        
        result = v0 * (1 - z_fract) + v1 * z_fract
        result = (result - 0.5) * 1 + 0.3
        
        return max(0, min(1, result))

perlin = ProcessingStyleNoise()

def pde_noise(x, y=0, z=0):
    return perlin.noise(x, y, z)

# 視覺矩形動畫類
class VisualRect:
    def __init__(self, x, y, w, h, config):
        self.config = config
        face_size = max(w, h)
        
        size_multiplier = self.config.get_float('BASIC', 'frame_size_multiplier', 1.3)
        
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
        
        self.is_flickering = False
        
        self.state1_end = self.state1_duration
        self.state2_end = self.state1_end + self.state2_duration
        self.state3_end = self.state2_end + self.state3_duration
        self.state4_end = self.state3_end + self.state4_duration
        
    def update(self, target_x, target_y, target_w, target_h):
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
        corner_length = self.config.get_float('STATE1', 'corner_length_ratio', 0.07)
        line_thickness = self.config.get_int('STATE1', 'line_thickness', 1)
        
        center_x = int(self.x)
        center_y = int(self.y)
        half_w = int(self.outside_w * 0.5)
        half_h = int(self.outside_h * 0.5)
        corner_len_w = int(self.outside_w * corner_length)
        corner_len_h = int(self.outside_h * corner_length)
        
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
        cross_length_h = self.config.get_float('STATE3', 'cross_length_ratio_h', 0.59)
        cross_length_w = self.config.get_float('STATE3', 'cross_length_ratio_w', 0.55)
        line_thickness = self.config.get_int('STATE4', 'line_thickness', 2)
        
        start_h = int(self.start_line * self.h * cross_length_h)
        end_h = int(self.end_line * self.h * cross_length_h)
        start_w = int(self.start_line * self.w * cross_length_w)
        end_w = int(self.end_line * self.w * cross_length_w)
        
        cv2.line(frame, (int(self.x), int(self.y - start_h)),
                (int(self.x), int(self.y - end_h)), color, line_thickness)
        cv2.line(frame, (int(self.x), int(self.y + start_h)),
                (int(self.x), int(self.y + end_h)), color, line_thickness)
        cv2.line(frame, (int(self.x + start_w), int(self.y)),
                (int(self.x + end_w), int(self.y)), color, line_thickness)
        cv2.line(frame, (int(self.x - start_w), int(self.y)),
                (int(self.x - end_w), int(self.y)), color, line_thickness)

# 改進的窗口類
class ImprovedCalWindow:
    def __init__(self, center_x, center_y, face_size, window_type_sequence=None):
        self.position_fixed = False
        self.fixed_x = None
        self.fixed_y = None
        
        self.center_x = center_x
        self.center_y = center_y
        self.face_size = face_size
        
        self.spawn_center_x = center_x
        self.spawn_center_y = center_y
        
        base_width = 160
        base_height = 100
        size_multiplier = random.uniform(0.9, 1.1)
        self.width = int(base_width * size_multiplier)
        self.height = int(base_height * size_multiplier)
        
        self.base_alpha = random.randint(180, 255)
        
        if window_type_sequence is not None:
            self.window_kind = window_type_sequence
        else:
            self.window_kind = random.randint(1, 16)
            
        self.life = random.randint(200, 400)
        self.max_life = self.life
        self.display = True
        
        self.i = random.randint(0, 1000)
        self.alpha = 1.0
        self.mode = 3
        
        self.force_flicker = False
        self.detection_state = 0
        
    def update_position(self):
        if not self.position_fixed:
            self.fixed_x = self.x
            self.fixed_y = self.y
            self.position_fixed = True
    
    def update_center(self, new_center_x, new_center_y):
        self.center_x = new_center_x
        self.center_y = new_center_y
        
        if self.position_fixed:
            self.x = self.fixed_x
            self.y = self.fixed_y
        
    def set_force_flicker(self, should_flicker):
        self.force_flicker = should_flicker
        
    def set_detection_state(self, state):
        self.detection_state = state
        
    def update(self):
        global frame_count
        
        self.life -= 1
        
        if self.life >= self.max_life * 0.8:
            self.mode = 3
        elif self.life >= self.max_life * 0.2:
            self.mode = 2
        elif self.life > 0:
            self.mode = 1
        else:
            self.mode = 0
            
        if self.force_flicker:
            self.display = False
            self.alpha = 0.0
        elif self.mode == 3:
            self.display = (self.life % 2 == 0)
            self.alpha = 1.0
        elif self.mode == 2:
            self.display = True
            self.alpha = 1.0
        elif self.mode == 1:
            self.display = (self.life % 2 == 0)
            self.alpha = 1.0
        else:
            self.display = False
            self.alpha = 0.0
            
        return self.life > 0
    
    def draw_on_cv_frame(self, frame, color_bgr=(255, 255, 255)):
        if self.detection_state < 3:
            return
            
        if not self.display:
            return
            
        # 繪製連接線 - 增加透明度
        connection_alpha = int(120 * self.alpha)  # 增加從50到120
        connection_color = tuple(int(c * connection_alpha / 255) for c in color_bgr)
        
        cv2.line(frame, 
                (int(self.x), int(self.y)), 
                (int(self.spawn_center_x), int(self.spawn_center_y)), 
                connection_color, 1)
        
        frame_alpha = int(self.base_alpha * self.alpha)
        window_color = tuple(int(c * frame_alpha / 255) for c in color_bgr)
        
        wx = int(self.x - self.width/2)
        wy = int(self.y - self.height/2)
        cv2.rectangle(frame, (wx, wy), (wx + self.width, wy + self.height), window_color, 1)
        
        inner_x = int(self.x - self.width * 0.46)
        inner_y = int(self.y - self.height * 0.4)
        inner_w = int(self.width * 0.92)
        inner_h = int(self.height * 0.8)
        cv2.rectangle(frame, (inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h), window_color, 1)
        
        cv2.rectangle(frame, (wx + 6, wy + 3), (wx + 12, wy + 9), window_color, 1)
        cv2.rectangle(frame, (wx + 20, wy + 3), (wx + 26, wy + 9), window_color, 1)
        
        self.draw_content_on_cv(frame, int(self.x), int(self.y), window_color)
        
    def draw_content_on_cv(self, frame, cx, cy, color):
        global frame_count
        
        if self.window_kind == 1:
            self.draw_bar_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 2:
            self.draw_line_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 3:
            self.draw_curve_chart_cv(frame, cx, cy, color)
        elif self.window_kind == 4:
            self.draw_matrix_display_cv(frame, cx, cy, color)
        elif self.window_kind == 5:
            self.draw_geometric_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 6:
            self.draw_grid_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 7:
            self.draw_oscilloscope_cv(frame, cx, cy, color)
        elif self.window_kind == 8:
            self.draw_radar_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 9:
            self.draw_complex_shapes_cv(frame, cx, cy, color)
        elif self.window_kind == 10:
            self.draw_crosshair_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 11:
            self.draw_diamond_shapes_cv(frame, cx, cy, color)
        elif self.window_kind == 12:
            self.draw_level_indicators_cv(frame, cx, cy, color)
        elif self.window_kind == 13:
            self.draw_progress_bars_cv(frame, cx, cy, color)
        elif self.window_kind == 14:
            self.draw_vertical_oscilloscope_cv(frame, cx, cy, color)
        elif self.window_kind == 15:
            self.draw_orbital_pattern_cv(frame, cx, cy, color)
        elif self.window_kind == 16:
            self.draw_stacked_bars_cv(frame, cx, cy, color)
    
    def draw_bar_chart_cv(self, frame, cx, cy, color):
        for i in range(16):
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            bar_height = int(70 * noise_val)
            bar_x = int(cx - 70 + i * 9)
            bar_y = int(cy + 40)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 6, bar_y - bar_height), color, -1)
    
    def draw_line_chart_cv(self, frame, cx, cy, color):
        points = []
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        for i in range(15):
            cv2.line(frame, points[i], points[i+1], color, 1)
        
        for px, py in points:
            cv2.circle(frame, (px, py), 2, color, -1)
    
    def draw_curve_chart_cv(self, frame, cx, cy, color):
        points = []
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        for i in range(len(points) - 1):
            cv2.line(frame, points[i], points[i+1], color, 1)
        
        cv2.line(frame, (int(cx - 67), int(cy + 8)), 
                 (int(cx + 77), int(cy + 8)), color, 1)
        
        for i in range(16):
            px, py = points[i]
            cv2.line(frame, (px, int(cy + 8)), (px, py), color, 1)
    
    def draw_matrix_display_cv(self, frame, cx, cy, color):
        for i in range(9):
            for j in range(3):
                noise_val = pde_noise(i, j, frame_count * CONTENT_ANIMATION_SPEED)
                text_val = int(noise_val * 10)
                body_val = int(noise_val * 20)
                px = int(cx - 62.5 + i * 15)
                py = int(cy - 25 + j * 20)
                self.draw_shaba_text_cv(frame, text_val, body_val, px, py, color)
    
    def draw_shaba_text_cv(self, frame, tag_point, tag_body, px, py, color):
        if tag_point == 1:
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, -1)
        elif tag_point == 2:
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, -1)
        elif tag_point == 3:
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, -1)
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, -1)
        
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
        for j in range(8):
            fill_noise = pde_noise(self.i + j, frame_count * CONTENT_ANIMATION_SPEED)
            if fill_noise > 0.5:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in color)
            else:
                fill_color = None
            
            if j == 0:
                points = np.array([
                    [cx, cy - 30], 
                    [cx - 20, cy + 30], 
                    [cx + 20, cy + 30]
                ], np.int32)
            elif j == 1:
                points = np.array([
                    [cx + 10, cy - 3], 
                    [cx + 30, cy - 30], 
                    [cx + 65, cy - 30], 
                    [cx + 65, cy - 20]
                ], np.int32)
            elif j == 2:
                points = np.array([
                    [cx + 10, cy + 5], 
                    [cx + 65, cy - 10], 
                    [cx + 65, cy + 10]
                ], np.int32)
            elif j == 3:
                points = np.array([
                    [cx + 10, cy + 13], 
                    [cx + 65, cy + 20], 
                    [cx + 65, cy + 35], 
                    [cx + 30, cy + 35]
                ], np.int32)
            elif j == 4:
                points = np.array([
                    [cx, cy + 10], 
                    [cx + 20, cy + 35], 
                    [cx - 20, cy + 35]
                ], np.int32)
            elif j == 5:
                points = np.array([
                    [cx - 10, cy + 13], 
                    [cx - 30, cy + 35], 
                    [cx - 65, cy + 35], 
                    [cx - 65, cy + 20]
                ], np.int32)
            elif j == 6:
                points = np.array([
                    [cx - 10, cy + 5], 
                    [cx - 65, cy + 10], 
                    [cx - 65, cy - 10]
                ], np.int32)
            else:
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
        for i in range(4):
            temp_value = pde_noise(i + 2, frame_count * 0.01)
            line_y = int(cy - 15 + i * 15)
            cv2.line(frame, (int(cx - 64), line_y), (int(cx + 64), line_y), color, 1)
            
            dot_x = int(cx - 64 + temp_value * 128)
            cv2.circle(frame, (dot_x, line_y), 2, color, -1)
    
    def draw_radar_pattern_cv(self, frame, cx, cy, color):
        cv2.circle(frame, (cx, cy), 5, color, -1)
        cv2.line(frame, (int(cx - 64), cy), (int(cx + 64), cy), color, 1)
        
        for i in range(6):
            temp_value = pde_noise(i + 8, frame_count * 0.02)
            radius = 10 + i * 5
            start_angle = int(360 * temp_value)
            span_angle = 30 + i * 8
            
            cv2.ellipse(frame, (cx, cy), (radius, radius), 0, start_angle, start_angle + span_angle, color, 1)
    
    def draw_complex_shapes_cv(self, frame, cx, cy, color):
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
        temp_x1 = pde_noise(self.i + 110, frame_count * 0.013)
        temp_y1 = pde_noise(self.i + 111, frame_count * 0.012)
        temp_x2 = pde_noise(self.i + 112, frame_count * 0.014)
        temp_y2 = pde_noise(self.i + 113, frame_count * 0.015)
        
        line_y1 = int(cy + temp_y1 * 90 - 45)
        line_x1 = int(cx + temp_x1 * 160 - 80)
        cv2.line(frame, (int(cx - 72), line_y1), (int(cx + 72), line_y1), color, 1)
        cv2.line(frame, (line_x1, int(cy - 35)), (line_x1, int(cy + 40)), color, 1)
        
        mark_alpha = int(100 * self.alpha)
        mark_color = tuple(int(c * mark_alpha / 255) for c in (255, 255, 255))
        
        offsets = [(0.02, -0.03), (0.05, -0.03), (-0.02, -0.03), (-0.05, -0.03),
                   (0.02, 0.03), (0.05, 0.03), (-0.02, 0.03), (-0.05, 0.03)]
        
        for dx, dy in offsets:
            mark_x = int(cx - 80 + (temp_x1 + dx) * 160)
            mark_y = int(cy + (temp_y1 + dy) * 90 - 45)
            if abs(dx) > abs(dy):
                cv2.line(frame, (mark_x - 3, mark_y), (mark_x + 3, mark_y), mark_color, 1)
            else:
                cv2.line(frame, (mark_x, mark_y - 4), (mark_x, mark_y + 4), mark_color, 1)
        
        line_y2 = int(cy + temp_y2 * 90 - 45)
        line_x2 = int(cx + temp_x2 * 160 - 80)
        cv2.line(frame, (int(cx - 72), line_y2), (int(cx + 72), line_y2), color, 1)
        cv2.line(frame, (line_x2, int(cy - 35)), (line_x2, int(cy + 40)), color, 1)
    
    def draw_diamond_shapes_cv(self, frame, cx, cy, color):
        shapes = [
            [(0, -30), (16, 2.5), (0, 35), (-16, 2.5)],
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
        temp_value = pde_noise(self.i + 13, frame_count * CONTENT_ANIMATION_SPEED) * 15 - 1
        
        for i in range(13):
            if i <= temp_value:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
                bar_y = int(cy + 35 - 5 * i)
                bar_h = 5
                cv2.rectangle(frame, (int(cx - 8), bar_y - bar_h), 
                             (int(cx + 8), bar_y), fill_color, -1)
            else:
                bar_y = int(cy + 35 - 5 * i)
                bar_h = 5
                cv2.rectangle(frame, (int(cx - 8), bar_y - bar_h), 
                             (int(cx + 8), bar_y), color, 1)
        
        for i in range(0, 13, 2):
            mark_y = int(cy + 35 - 5 * i)
            cv2.circle(frame, (int(cx - 16), mark_y), 2, color, -1)
            cv2.circle(frame, (int(cx + 16), mark_y), 2, color, -1)
    
    def draw_progress_bars_cv(self, frame, cx, cy, color):
        for i in range(4):
            temp_value = pde_noise(i + 1, frame_count * CONTENT_ANIMATION_SPEED)
            bar_y = int(cy - 25 + 15 * i)
            bar_h = 10
            
            filled_width = int(temp_value * 128) - 2
            cv2.rectangle(frame, (int(cx - 64), bar_y), 
                         (int(cx - 64) + filled_width, bar_y + bar_h), color, -1)
            
            empty_start = int(cx - 64) + filled_width + 3
            empty_width = 128 - filled_width - 3
            cv2.rectangle(frame, (empty_start, bar_y), (empty_start + empty_width, bar_y + bar_h), color, 1)
    
    def draw_vertical_oscilloscope_cv(self, frame, cx, cy, color):
        for i in range(16):
            bar_x = int(cx - 70 + i * 9)
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 - 35 * noise_val)), color, 1)
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 + 35 * noise_val)), color, 1)
    
    def draw_orbital_pattern_cv(self, frame, cx, cy, color):
        temp_values = [
            pde_noise(self.i + 215, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 216, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 217, frame_count * CONTENT_ANIMATION_SPEED)
        ]
        
        center_x = int(cx - 24)
        center_y = int(cy + 5)
        
        r1 = 8
        cv2.circle(frame, (center_x, center_y), r1, color, 1)
        r2 = 20
        cv2.circle(frame, (center_x, center_y), r2, color, 1)
        r3 = 32
        cv2.circle(frame, (center_x, center_y), r3, color, 1)
        
        base_x = int(cx - 8)
        base_y = int(cy + 5)
        
        radii = [8, 20, 32]
        for i, (radius, temp_val) in enumerate(zip(radii, temp_values)):
            angle_rad = math.radians(temp_val * 360)
            orbit_x = int(radius * math.cos(angle_rad)) + center_x
            orbit_y = int(radius * math.sin(angle_rad)) + center_y
            
            cv2.line(frame, (base_x, base_y), (orbit_x, orbit_y), color, 1)
            
            point_r = 4
            cv2.circle(frame, (orbit_x, orbit_y), point_r, color, 1)
    
    def draw_stacked_bars_cv(self, frame, cx, cy, color):
        temp_values = [
            pde_noise(self.i + 215, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 216, frame_count * CONTENT_ANIMATION_SPEED),
            pde_noise(self.i + 217, frame_count * CONTENT_ANIMATION_SPEED)
        ]
        
        for i in range(14):
            line_y = int(cy - 30 + i * 5)
            cv2.line(frame, (int(cx - 64), line_y), 
                     (int(cx + 64), line_y), color, 1)
        
        fill_alpha = int(100 * self.alpha)
        fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
        
        bar_height = int(temp_values[0] * 90)
        cv2.rectangle(frame, (int(cx - 40), int(cy + 40)), 
                     (int(cx - 24), int(cy + 40) - bar_height), fill_color, -1)
        
        bar_height = int(temp_values[1] * 90)
        cv2.rectangle(frame, (int(cx - 8), int(cy + 40)), 
                     (int(cx + 8), int(cy + 40) - bar_height), fill_color, -1)
        
        bar_height = int(temp_values[2] * 90)
        cv2.rectangle(frame, (int(cx + 24), int(cy + 40)), 
                     (int(cx + 40), int(cy + 40) - bar_height), fill_color, -1)

class ImprovedDetectionWindowEffect:
    def __init__(self, screen_width=1080, screen_height=1920):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.windows_by_face = {}
        self.center_points_by_face = {}
        self.spawn_rate = 0.1
        
        self.face_states = {}
        self.window_spawn_delays = {}
        self.max_windows_per_face = 8
        self.spawn_delay_frames = 30
        
        self.window_type_counters = {}
        self.window_type_sequences = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, 16]
        ]
        
        self.used_points_by_face = {}
        
    def update_faces(self, faces, face_states=None):
        current_face_ids = set(range(len(faces)))
        
        for face_id in list(self.windows_by_face.keys()):
            if face_id not in current_face_ids:
                del self.windows_by_face[face_id]
                if face_id in self.center_points_by_face:
                    del self.center_points_by_face[face_id]
                if face_id in self.face_states:
                    del self.face_states[face_id]
                if face_id in self.window_spawn_delays:
                    del self.window_spawn_delays[face_id]
                if face_id in self.window_type_counters:
                    del self.window_type_counters[face_id]
                if face_id in self.used_points_by_face:
                    del self.used_points_by_face[face_id]
        
        if face_states:
            for face_id, state in face_states.items():
                if face_id in current_face_ids:
                    old_state = self.face_states.get(face_id, 0)
                    self.face_states[face_id] = state
                    
                    if state == 3 and old_state < 3:
                        self.window_spawn_delays[face_id] = 0
                        self.window_type_counters[face_id] = 0
        
        for i, (x, y, w, h) in enumerate(faces):
            center_x = x + w // 2
            center_y = y + h // 2
            face_size = max(w, h)
            
            if i not in self.windows_by_face:
                self.windows_by_face[i] = []
                self.generate_center_points_for_face(i, center_x, center_y, face_size)
                self.window_type_counters[i] = 0
                self.used_points_by_face[i] = []
            
            # 清理已死亡的窗口
            dead_windows = []
            for window in self.windows_by_face[i]:
                if window.life <= 0:
                    # 找到對應的點索引並釋放
                    for idx, point in enumerate(self.center_points_by_face[i]):
                        if (abs(window.spawn_center_x - point[0]) < 5 and 
                            abs(window.spawn_center_y - point[1]) < 5):
                            if idx in self.used_points_by_face[i]:
                                self.used_points_by_face[i].remove(idx)
                            break
                    dead_windows.append(window)
            
            # 移除死亡的窗口
            for window in dead_windows:
                self.windows_by_face[i].remove(window)
            
            # 更新現有窗口
            for window in self.windows_by_face[i]:
                window.update_center(center_x, center_y)
            
            # 更新點的位置
            self.update_points_position(i, center_x, center_y, face_size)
            
            can_spawn = self._can_spawn_window(i)
            
            if can_spawn and len(self.windows_by_face[i]) < self.max_windows_per_face:
                self.spawn_new_window(i, center_x, center_y, face_size)
            
            # 更新現有窗口
            for window in self.windows_by_face[i]:
                window.update()
    
    def update_points_position(self, face_id, center_x, center_y, face_size):
        """更新點的位置，讓它們跟隨人臉移動"""
        if face_id not in self.center_points_by_face:
            return
            
        # 重新生成點的位置，保持相對於檢測框的位置
        frame_size = face_size * 1.3
        frame_half_size = frame_size * 0.5
        
        # 定義八個點的偏移比例（每個象限2個點）
        quadrant_offsets = [
            # 左上象限 - 2個點
            (-0.35 * 0.7, -0.35 * 0.7),  # 內圈
            (-0.35 * 1.3, -0.35 * 1.3),  # 外圈
            
            # 右上象限 - 2個點
            (0.35 * 0.7, -0.35 * 0.7),   # 內圈
            (0.35 * 1.3, -0.35 * 1.3),   # 外圈
            
            # 右下象限 - 2個點
            (0.35 * 0.7, 0.35 * 0.7),    # 內圈
            (0.35 * 1.3, 0.35 * 1.3),    # 外圈
            
            # 左下象限 - 2個點
            (-0.35 * 0.7, 0.35 * 0.7),   # 內圈
            (-0.35 * 1.3, 0.35 * 1.3),   # 外圈
        ]
        
        updated_points = []
        for i, (offset_x, offset_y) in enumerate(quadrant_offsets):
            # 基於檢測框中心和大小計算點的位置
            point_x = center_x + frame_half_size * offset_x
            point_y = center_y + frame_half_size * offset_y
            
            # 加入小的隨機偏移
            point_x += random.uniform(-face_size * 0.05, face_size * 0.05)
            point_y += random.uniform(-face_size * 0.05, face_size * 0.05)
            
            # 確保在屏幕範圍內
            point_x = max(150, min(self.screen_width - 150, point_x))
            point_y = max(150, min(self.screen_height - 150, point_y))
            
            updated_points.append((int(point_x), int(point_y)))
        
        self.center_points_by_face[face_id] = updated_points
        
        # 更新現有窗口的連接點
        for i, window in enumerate(self.windows_by_face[face_id]):
            # 找到窗口對應的點索引
            for idx, point in enumerate(updated_points):
                if idx in self.used_points_by_face[face_id]:
                    # 檢查這個點是否是當前窗口的連接點
                    old_point = self.center_points_by_face[face_id][idx] if idx < len(self.center_points_by_face[face_id]) else None
                    if old_point and hasattr(window, 'point_index') and window.point_index == idx:
                        window.spawn_center_x = point[0]
                        window.spawn_center_y = point[1]
    
    def spawn_new_window(self, face_id, center_x, center_y, face_size):
        """生成新窗口"""
        if face_id not in self.center_points_by_face:
            return
            
        # 找到未使用的點
        available_points = []
        for idx in range(len(self.center_points_by_face[face_id])):
            if idx not in self.used_points_by_face[face_id]:
                available_points.append(idx)
        
        if not available_points:
            # 如果沒有可用的點，重新生成
            self.generate_center_points_for_face(face_id, center_x, center_y, face_size)
            self.used_points_by_face[face_id] = []
            available_points = list(range(8))
        
        # 選擇一個點
        point_index = available_points[0]
        spawn_center = self.center_points_by_face[face_id][point_index]
        
        # 標記這個點為已使用
        self.used_points_by_face[face_id].append(point_index)
        
        # 獲取窗口類型
        window_type = self._get_next_window_type(face_id)
        
        # 在對應象限生成窗口位置
        win_x, win_y = self._generate_window_position_in_quadrant(
            center_x, center_y, face_size, point_index
        )
        
        new_window = ImprovedCalWindow(win_x, win_y, face_size, window_type)
        new_window.x = win_x
        new_window.y = win_y
        new_window.spawn_center_x = spawn_center[0]
        new_window.spawn_center_y = spawn_center[1]
        new_window.point_index = point_index  # 記錄使用的點索引
        new_window.update_position()
        
        self.windows_by_face[face_id].append(new_window)
        
        # 重置延遲計時器
        if face_id in self.window_spawn_delays:
            self.window_spawn_delays[face_id] = -45
    
    def _get_next_window_type(self, face_id):
        if face_id not in self.window_type_counters:
            self.window_type_counters[face_id] = 0
        
        counter = self.window_type_counters[face_id]
        sequence_index = (counter // 4) % len(self.window_type_sequences)
        type_index = counter % 4
        
        window_type = self.window_type_sequences[sequence_index][type_index]
        
        self.window_type_counters[face_id] += 1
        
        return window_type
    
    def _can_spawn_window(self, face_id):
        if face_id not in self.face_states:
            return False
            
        current_state = self.face_states[face_id]
        if current_state < 3:
            return False
        
        if face_id not in self.window_spawn_delays:
            return False
            
        if self.window_spawn_delays[face_id] < self.spawn_delay_frames:
            self.window_spawn_delays[face_id] += 1
            return False
        
        if self.window_spawn_delays[face_id] < 0:
            self.window_spawn_delays[face_id] += 1
            return False
        
        spawn_chance = self.spawn_rate * 0.3
        return random.random() < spawn_chance
    
    def generate_center_points_for_face(self, face_id, center_x, center_y, face_size):
        """生成8個分散在四個角落的點，每個角落有2個點"""
        center_points = []
        
        frame_size = face_size * 1.3
        frame_half_size = frame_size * 0.5
        
        # 每個象限的兩個點偏移（內圈和外圈）
        quadrant_offsets = [
            # 左上象限 - 2個點
            (-0.35 * 0.7, -0.35 * 0.7),  # 內圈
            (-0.35 * 1.3, -0.35 * 1.3),  # 外圈
            
            # 右上象限 - 2個點
            (0.35 * 0.7, -0.35 * 0.7),   # 內圈
            (0.35 * 1.3, -0.35 * 1.3),   # 外圈
            
            # 右下象限 - 2個點
            (0.35 * 0.7, 0.35 * 0.7),    # 內圈
            (0.35 * 1.3, 0.35 * 1.3),    # 外圈
            
            # 左下象限 - 2個點
            (-0.35 * 0.7, 0.35 * 0.7),   # 內圈
            (-0.35 * 1.3, 0.35 * 1.3),   # 外圈
        ]
        
        for offset_x, offset_y in quadrant_offsets:
            # 基礎位置
            base_x = center_x + frame_half_size * offset_x
            base_y = center_y + frame_half_size * offset_y
            
            # 加入小的隨機偏移
            x = base_x + random.uniform(-face_size * 0.05, face_size * 0.05)
            y = base_y + random.uniform(-face_size * 0.05, face_size * 0.05)
            
            # 確保在屏幕範圍內
            x = max(150, min(self.screen_width - 150, x))
            y = max(150, min(self.screen_height - 150, y))
            
            center_points.append((int(x), int(y)))
        
        self.center_points_by_face[face_id] = center_points
    
    def _generate_window_position_in_quadrant(self, center_x, center_y, face_size, point_index):
        """在對應點附近生成窗口位置"""
        base_distance = face_size * 1.5
        
        # 根據點索引確定象限和內外圈
        quadrant_index = point_index // 2  # 0-3 對應四個象限
        is_outer = point_index % 2 == 1    # 奇數為外圈，偶數為內圈
        
        # 每個象限的角度範圍
        angle_ranges = [
            (180, 270),  # 左上
            (270, 360),  # 右上
            (0, 90),     # 右下
            (90, 180)    # 左下
        ]
        
        angle_range = angle_ranges[quadrant_index]
        angle = random.uniform(angle_range[0], angle_range[1])
        angle_rad = math.radians(angle)
        
        # 根據內外圈調整距離
        if is_outer:
            distance_multiplier = 1.3  # 外圈距離更遠
        else:
            distance_multiplier = 0.9  # 內圈距離更近
        
        distance = base_distance * distance_multiplier + random.uniform(0, face_size * 0.3)
        win_x = center_x + distance * math.cos(angle_rad)
        win_y = center_y + distance * math.sin(angle_rad)
        
        window_margin = 100
        win_x = max(window_margin, min(self.screen_width - window_margin, win_x))
        win_y = max(window_margin, min(self.screen_height - window_margin, win_y))
        
        return int(win_x), int(win_y)
    
    def set_flicker_state_for_face(self, face_id, should_flicker):
        if face_id in self.windows_by_face:
            for window in self.windows_by_face[face_id]:
                window.set_force_flicker(should_flicker)
    
    def draw_all_windows(self, frame, color_bgr=(255, 255, 255)):
        """只繪製窗口，不繪製點"""
        for face_id, windows in self.windows_by_face.items():
            for window in windows:
                if face_id in self.face_states:
                    window.set_detection_state(self.face_states[face_id])
                window.draw_on_cv_frame(frame, color_bgr)
    
    def get_total_window_count(self):
        return sum(len(windows) for windows in self.windows_by_face.values())
    
    def clear_all_windows(self):
        self.windows_by_face.clear()
        self.center_points_by_face.clear()
        self.face_states.clear()
        self.window_spawn_delays.clear()
        self.window_type_counters.clear()
        self.used_points_by_face.clear()

# 檢測覆蓋層類
class DebugDetectionOverlay:
    def __init__(self):
        self.anim_config = AnimConfigLoader()
        
        config_errors = self.anim_config.validate_config()
        if config_errors:
            for key, error in config_errors.items():
                print(f"  {error}")
        
        self.visual_rects = []
        self.window_effect = ImprovedDetectionWindowEffect(screen_width=1080, screen_height=1920)
    
    def update_visual_rects_main_loop(self, faces):
        while len(self.visual_rects) > len(faces):
            self.visual_rects.pop()
        
        while len(self.visual_rects) < len(faces):
            if len(faces) > len(self.visual_rects):
                x, y, w, h = faces[len(self.visual_rects)]
                center_x = x + w // 2
                center_y = y + h // 2
                rect = VisualRect(center_x, center_y, w, h, self.anim_config)
                self.visual_rects.append(rect)
        
        face_states = {}
        for i, (x, y, w, h) in enumerate(faces):
            if i < len(self.visual_rects):
                center_x = x + w // 2
                center_y = y + h // 2
                self.visual_rects[i].update(center_x, center_y, w, h)
                
                face_states[i] = self.visual_rects[i].state
        
        self.window_effect.update_faces(faces, face_states)
        
        for i, rect in enumerate(self.visual_rects):
            if hasattr(rect, 'is_flickering'):
                self.window_effect.set_flicker_state_for_face(i, rect.is_flickering)
            if i in self.window_effect.windows_by_face:
                for window in self.window_effect.windows_by_face[i]:
                    window.set_detection_state(rect.state)
    
    def draw_on_frame(self, frame):
        color_bgr = self.anim_config.get_color_bgr()
        
        for rect in self.visual_rects:
            rect.draw(frame)
        
        self.window_effect.draw_all_windows(frame, color_bgr)
        
        return frame
    
    def clear_all_effects(self):
        self.visual_rects.clear()
        self.window_effect.clear_all_windows()
    
    def reload_config(self):
        self.anim_config.reload_config()
    
    def get_animation_info(self):
        info = {
            'rect_count': len(self.visual_rects),
            'window_count': self.window_effect.get_total_window_count(),
            'current_state': self.visual_rects[0].state if self.visual_rects else 0,
            'is_flickering': self.visual_rects[0].is_flickering if self.visual_rects else False
        }
        return info

# 真實人臉檢測器
try:
    import mediapipe as mp
    mp_face_detection = mp.solutions.face_detection
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False

class RealFaceDetector:
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
                
            except Exception as e:
                print(f"人臉檢測器初始化失敗: {e}")
                self.face_detection = None
    
    def process_frame(self, frame):
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

# 攝像頭處理器
class CameraProcessor(QThread):
    frame_ready = pyqtSignal(np.ndarray, list)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.use_camera = False
        self.camera = None
        self.frame_count = 0
        
        self.face_detector = RealFaceDetector()
        
        self.simulate_faces = True  # 默認使用模擬
        self.face_positions = []
        self.init_face_movement()
        
        self.detection_overlay = DebugDetectionOverlay()
        
        self.try_enable_camera()
        
    def init_face_movement(self):
        self.face_center_x = 540
        self.face_center_y = 960
        self.face_velocity_x = random.uniform(-2, 2)
        self.face_velocity_y = random.uniform(-2, 2)
        
    def try_enable_camera(self):
        try:
            test_camera = cv2.VideoCapture(0)
            if test_camera.isOpened():
                ret, _ = test_camera.read()
                if ret:
                    self.camera = test_camera
                    self.use_camera = True
                else:
                    test_camera.release()
            else:
                test_camera.release()
        except Exception as e:
            pass
    
    def generate_moving_face(self):
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
            
            self.detection_overlay.update_visual_rects_main_loop(faces)
            
            final_frame = self.detection_overlay.draw_on_frame(frame)
            
            self.frame_ready.emit(final_frame, faces)
            
            if self.simulate_faces:
                self.generate_moving_face()
            
            self.frame_count += 1
            global frame_count
            frame_count += 1
            self.msleep(16)
    
    def process_camera_frame(self, raw_frame):
        height, width = raw_frame.shape[:2]
        
        if width == 1080 and height == 1920:
            return raw_frame
        
        if width != 1920 or height != 1080:
            raw_frame = cv2.resize(raw_frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        target_crop_width = 607
        crop_x = 656
        crop_y = 0
        
        cropped_frame = raw_frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
    
    def generate_test_frame(self):
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

# 主調試窗口
class CalWindowsDebugWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUI()
        self.setupCamera()
        
    def setupUI(self):
        self.setWindowTitle("Cal Windows Debug Tool")
        
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
        self.camera_processor = CameraProcessor()
        self.camera_processor.frame_ready.connect(self.update_frame)
        self.camera_processor.start()
        
    def update_frame(self, frame, faces):
        try:
            self.display_frame(frame)
        except Exception as e:
            print(f"更新畫面時發生錯誤: {e}")
    
    def display_frame(self, frame):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        self.camera_label.setPixmap(pixmap)
    
    def closeEvent(self, event):
        self.camera_processor.stop()
        self.camera_processor.wait()
        event.accept()

# 主函數
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    debug_window = CalWindowsDebugWindow()
    debug_window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

