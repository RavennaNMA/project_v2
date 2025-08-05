# Location: project_v2/ui/cal_windows_effect.py
# Usage: 改進的 Cal Windows Effect - 整合到主程序

import cv2
import numpy as np
import random
import math
import time
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from utils import AnimConfigLoader

# 全域frame_count變數
frame_count = 0

def update_global_frame_count():
    """更新全域幀計數"""
    global frame_count
    frame_count += 1
    return frame_count

def get_global_frame_count():
    """獲取全域幀計數"""
    global frame_count
    return frame_count

# 簡化的噪聲函數，提高性能
class SimpleNoise:
    def __init__(self):
        self.seed = random.randint(0, 10000)
        
    def noise(self, x, y=0, z=0):
        # 簡化的 noise 實現，提高性能
        x_int = int(x * 1000)
        y_int = int(y * 1000)
        z_int = int(z * 1000)
        
        # 簡單的雜湊函數
        hash_val = (x_int * 73856093) ^ (y_int * 19349663) ^ (z_int * 83492791) ^ self.seed
        hash_val = (hash_val * 1664525 + 1013904223) % (2**32)
        
        # 返回 0-1 範圍的值
        result = (hash_val / (2**32)) * 0.6 + 0.2  # 調整範圍到 0.2-0.8
        return max(0, min(1, result))

noise_generator = SimpleNoise()

def pde_noise(x, y=0, z=0):
    return noise_generator.noise(x, y, z)

# 改進的窗口類
class ImprovedCalWindow:
    def __init__(self, center_x, center_y, face_size, window_type_sequence=None, config=None):
        self.config = config or AnimConfigLoader()

        # 從配置獲取動畫速度（重新載入配置以確保最新設定）
        self.config.reload_config()
        self.content_animation_speed = self.config.get_float('ANIMATION', 'content_animation_speed', 0.1)
        print(f"Cal Window 動畫速度設定: {self.content_animation_speed}")

        self.position_fixed = False
        self.fixed_x = None
        self.fixed_y = None
    
        self.center_x = center_x
        self.center_y = center_y
        self.face_size = face_size
        
        # 固定生成中心點，避免連接線抖動
        self.spawn_center_x = center_x
        self.spawn_center_y = center_y
        self.fixed_spawn_center_x = center_x
        self.fixed_spawn_center_y = center_y
        
        # 從配置獲取窗口大小
        base_width = self.config.get_int('VISUAL', 'window_width_base', 160)
        base_height = self.config.get_int('VISUAL', 'window_height_base', 100)
        size_multiplier_min = self.config.get_float('VISUAL', 'size_multiplier_min', 0.9)
        size_multiplier_max = self.config.get_float('VISUAL', 'size_multiplier_max', 1.1)
        
        size_multiplier = random.uniform(size_multiplier_min, size_multiplier_max)
        self.width = int(base_width * size_multiplier)
        self.height = int(base_height * size_multiplier)
        
        # 從配置獲取生命值
        min_life = self.config.get_int('BASIC', 'min_life', 200)
        max_life = self.config.get_int('BASIC', 'max_life', 400)
        self.life = random.randint(min_life, max_life)
        self.max_life = self.life
        
        # 從配置獲取透明度
        self.base_alpha = self.config.get_int('BASIC', 'window_alpha', 180)
        
        # 窗口類型
        if window_type_sequence is not None:
            self.window_kind = window_type_sequence
        else:
            self.window_kind = random.randint(1, 16)
            
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
        else:
            # 平滑更新窗口位置跟隨檢測框
            smooth_factor = self.config.get_float('BASIC', 'window_smooth_factor', 0.15)
            if hasattr(self, 'x') and hasattr(self, 'y'):
                self.x = self.x + (self.center_x - self.x) * smooth_factor
                self.y = self.y + (self.center_y - self.y) * smooth_factor
            else:
                self.x = self.center_x
                self.y = self.center_y
        
        # 更新固定生成點，讓連接線跟隨檢測框移動
        if hasattr(self, 'point_index') and hasattr(self, 'face_size'):
            # 根據檢測框的新位置重新計算生成點
            self._update_spawn_center_position()
    
    def _update_spawn_center_position(self):
        """根據檢測框位置更新生成點位置"""
        if not hasattr(self, 'point_index') or not hasattr(self, 'face_size'):
            return
            
        # 重新計算生成點位置（基於當前的檢測框中心）
        frame_size = self.face_size * 1.3
        frame_half_size = frame_size * 0.5
        
        # 定義四個象限的偏移比例
        quadrant_offsets = [
            (-0.35, -0.35),  # 左上
            (0.35, -0.35),   # 右上
            (0.35, 0.35),    # 右下
            (-0.35, 0.35)    # 左下
        ]
        
        if 0 <= self.point_index < len(quadrant_offsets):
            offset_x, offset_y = quadrant_offsets[self.point_index]
            
            # 基於檢測框中心和大小計算新的生成點位置
            new_spawn_x = self.center_x + frame_half_size * offset_x
            new_spawn_y = self.center_y + frame_half_size * offset_y
            
            # 加入小的隨機偏移（保持原有的隨機性）
            random_offset = self.face_size * 0.05
            new_spawn_x += random.uniform(-random_offset, random_offset)
            new_spawn_y += random.uniform(-random_offset, random_offset)
            
            # 平滑更新生成點位置
            smooth_factor = self.config.get_float('BASIC', 'spawn_point_smooth_factor', 0.12)
            if hasattr(self, 'spawn_center_x') and hasattr(self, 'spawn_center_y'):
                self.spawn_center_x = self.spawn_center_x + (new_spawn_x - self.spawn_center_x) * smooth_factor
                self.spawn_center_y = self.spawn_center_y + (new_spawn_y - self.spawn_center_y) * smooth_factor
            else:
                self.spawn_center_x = new_spawn_x
                self.spawn_center_y = new_spawn_y
            
            # 更新固定生成點位置
            self.fixed_spawn_center_x = self.spawn_center_x
            self.fixed_spawn_center_y = self.spawn_center_y
    
    def set_force_flicker(self, should_flicker):
        self.force_flicker = should_flicker
        
    def set_detection_state(self, state):
        self.detection_state = state
        
    def update(self):
        """更新窗口狀態"""
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
            
        # 繪製連接線 - 從配置獲取透明度
        connection_alpha = self.config.get_int('BASIC', 'connection_alpha', 120)
        connection_alpha = int(connection_alpha * self.alpha)
        connection_color = tuple(int(c * connection_alpha / 255) for c in color_bgr)
        
        # 根據配置決定使用哪個連接點
        use_stable_lines = self.config.get_bool('BASIC', 'stable_connection_lines', True)
        if use_stable_lines and hasattr(self, 'fixed_spawn_center_x'):
            # 使用固定的生成點，避免抖動
            line_start_x = int(self.fixed_spawn_center_x)
            line_start_y = int(self.fixed_spawn_center_y)
        else:
            # 使用動態生成點
            line_start_x = int(self.spawn_center_x)
            line_start_y = int(self.spawn_center_y)
        
        # 添加平滑連接線效果
        line_smooth_factor = self.config.get_float('BASIC', 'line_smooth_factor', 0.8)
        
        # 計算連接線的中間點，使線條更平滑
        mid_x = int(self.x + (line_start_x - self.x) * line_smooth_factor)
        mid_y = int(self.y + (line_start_y - self.y) * line_smooth_factor)
        
        # 繪製平滑的連接線（兩段線）
        cv2.line(frame, 
                (int(self.x), int(self.y)), 
                (mid_x, mid_y), 
                connection_color, 1)
        cv2.line(frame, 
                (mid_x, mid_y), 
                (line_start_x, line_start_y), 
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
        """繪製窗口內容"""
        current_frame = get_global_frame_count()
        
        if self.window_kind == 1:
            self.draw_bar_chart_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 2:
            self.draw_line_chart_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 3:
            self.draw_curve_chart_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 4:
            self.draw_matrix_display_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 5:
            self.draw_geometric_pattern_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 6:
            self.draw_grid_pattern_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 7:
            self.draw_oscilloscope_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 8:
            self.draw_radar_pattern_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 9:
            self.draw_complex_shapes_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 10:
            self.draw_crosshair_pattern_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 11:
            self.draw_diamond_shapes_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 12:
            self.draw_level_indicators_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 13:
            self.draw_progress_bars_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 14:
            self.draw_vertical_oscilloscope_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 15:
            self.draw_orbital_pattern_cv(frame, cx, cy, color, current_frame)
        elif self.window_kind == 16:
            self.draw_stacked_bars_cv(frame, cx, cy, color, current_frame)
    
    def draw_bar_chart_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的 Window 1: 柱狀圖
        for i in range(16):
            # 使用與舊版本相同的 noise 計算
            noise_val = pde_noise(i, current_frame * self.content_animation_speed)
            # 模擬 rect(-70+i*9, 40, 6, -70*noise(i, frameCount*0.1))
            bar_x = int(cx - 70 + i * 9)
            bar_y = int(cy + 40)
            bar_height = int(70 * noise_val)
            # 注意：Processing 的 rect 高度是負值，所以我們向上繪製
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 6, bar_y - bar_height), color, -1)
    
    def draw_line_chart_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的 Window 2: 線圖 + 圓點
        points = []
        
        # 計算所有點的位置
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, current_frame * self.content_animation_speed)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        # 繪製連接線 (模擬 line() 函數)
        for i in range(15):
            cv2.line(frame, points[i], points[i+1], color, 1)
        
        # 繪製圓點 (模擬 ellipse() 函數)
        for px, py in points:
            cv2.circle(frame, (px, py), 2, color, -1)  # 半徑 2，填充
    
    def draw_curve_chart_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的 Window 3: 曲線圖 + 垂直線
        points = []
        
        # 計算所有點的位置
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, current_frame * self.content_animation_speed)
            py = int(cy + 40 - 70 * noise_val)
            points.append((px, py))
        
        # 模擬 beginShape() 和 curveVertex()
        # 添加起始點 (curveVertex(-67.5, 40))
        curve_points = [(int(cx - 67.5), int(cy + 40))]
        
        # 添加所有數據點
        for px, py in points:
            curve_points.append((px, py))
        
        # 添加結束點 (curveVertex(76.5, 40))
        curve_points.append((int(cx + 76.5), int(cy + 40)))
        
        # 繪製曲線 (使用多邊形近似)
        if len(curve_points) > 2:
            curve_array = np.array(curve_points, np.int32)
            cv2.polylines(frame, [curve_array], False, color, 1)
        
        # 繪製底部水平線 (line(-67.5, 8, 76.5, 8))
        cv2.line(frame, (int(cx - 67.5), int(cy + 8)), (int(cx + 76.5), int(cy + 8)), color, 1)
        
        # 繪製垂直線 (line(-67.5+i*9, 8, -67.5+i*9, 40-70*noise(i, frameCount*0.1)))
        for i in range(16):
            px = int(cx - 67.5 + i * 9)
            noise_val = pde_noise(i, current_frame * self.content_animation_speed)
            py = int(cy + 40 - 70 * noise_val)
            cv2.line(frame, (px, int(cy + 8)), (px, py), color, 1)
    
    def draw_matrix_display_cv(self, frame, cx, cy, color, current_frame):
        # 使用與舊版本相同的邏輯：noFill() 和 stroke()
        for i in range(9):
            for j in range(3):
                # 使用與舊版本相同的 noise 計算
                noise_val = pde_noise(i, j, current_frame * self.content_animation_speed)
                text_val = int(noise_val * 10)
                body_val = int(noise_val * 20)
                px = int(cx - 62.5 + i * 15)
                py = int(cy - 25 + j * 20)
                self.draw_shaba_text_cv(frame, text_val, body_val, px, py, color)
    
    def draw_shaba_text_cv(self, frame, tag_point, tag_body, px, py, color):
        # 模擬 Processing 的 noFill() - 不填充矩形
        # 模擬 Processing 的 stroke() - 只畫邊框
        
        # 處理 Tag_Point (矩形部分)
        if tag_point == 1:
            # rect(0, 0, 2, 2) - 只畫邊框，不填充
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, 1)
        elif tag_point == 2:
            # rect(6, 0, 2, 2) - 只畫邊框，不填充
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, 1)
        elif tag_point == 3:
            # rect(0, 0, 2, 2) + rect(6, 0, 2, 2) - 只畫邊框，不填充
            cv2.rectangle(frame, (px, py), (px + 2, py + 2), color, 1)
            cv2.rectangle(frame, (px + 6, py), (px + 8, py + 2), color, 1)
        
        # 處理 Tag_Body (線條部分) - 模擬 beginShape() 和 endShape(CLOSE)
        tag_body = tag_body % 8
        
        # 創建點列表來模擬 beginShape() 和 endShape(CLOSE)
        points = []
        
        if tag_body == 0:
            # 創建封閉的多邊形
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 1, py + 11],  # 向下
                [px + 7, py + 11],  # 向右
                [px + 7, py + 5]    # 向上，回到起點
            ], np.int32)
        elif tag_body == 1:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 7, py + 5],   # 向右
                [px + 1, py + 5],   # 回到左邊
                [px + 1, py + 11],  # 向下
                [px + 7, py + 11]   # 向右
            ], np.int32)
        elif tag_body == 2:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 7, py + 5],   # 向右
                [px + 1, py + 5],   # 回到左邊
                [px + 1, py + 11],  # 向下
                [px + 7, py + 5]    # 對角線到右上
            ], np.int32)
        elif tag_body == 3:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 7, py + 5],   # 向右
                [px + 1, py + 11],  # 對角線到左下
                [px + 7, py + 11],  # 向右
                [px + 7, py + 5]    # 向上
            ], np.int32)
        elif tag_body == 4:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 7, py + 5],   # 向右
                [px + 1, py + 5],   # 回到左邊
                [px + 1, py + 11]   # 向下
            ], np.int32)
        elif tag_body == 5:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 1, py + 11],  # 向下
                [px + 7, py + 11]   # 向右
            ], np.int32)
        elif tag_body == 6:
            points = np.array([
                [px + 1, py + 11],  # 起點
                [px + 7, py + 11],  # 向右
                [px + 7, py + 5]    # 向上
            ], np.int32)
        elif tag_body == 7:
            points = np.array([
                [px + 1, py + 5],   # 起點
                [px + 7, py + 5],   # 向右
                [px + 7, py + 11]   # 向下
            ], np.int32)
        
        # 繪製封閉的多邊形（模擬 endShape(CLOSE)）
        if len(points) > 2:
            cv2.polylines(frame, [points], True, color, 1)
    
    def draw_geometric_pattern_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的 8 個幾何形狀
        for j in range(8):
            # 使用與舊版本相同的 noise 檢查
            fill_noise = pde_noise(self.i + j, current_frame * self.content_animation_speed)
            
            # 模擬 Processing 的 fill() 和 noFill()
            if fill_noise > 0.5:
                # 模擬 fill(255, 100*Enter_Light) - 使用 alpha 透明度
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in color)
            else:
                # 模擬 noFill() - 不填充
                fill_color = None
            
            # 根據舊版本的 8 個形狀創建對應的點陣列
            if j == 0:
                # 第一個形狀：三角形
                points = np.array([
                    [cx, cy],           # vertex(0, 0)
                    [cx - 20, cy - 30], # vertex(-20, -30)
                    [cx + 20, cy - 30]  # vertex(20, -30)
                ], np.int32)
            elif j == 1:
                # 第二個形狀：四邊形
                points = np.array([
                    [cx + 10, cy - 3],  # vertex(10, -3)
                    [cx + 30, cy - 30], # vertex(30, -30)
                    [cx + 65, cy - 30], # vertex(65, -30)
                    [cx + 65, cy - 20]  # vertex(65, -20)
                ], np.int32)
            elif j == 2:
                # 第三個形狀：三角形
                points = np.array([
                    [cx + 10, cy + 5],  # vertex(10, 5)
                    [cx + 65, cy - 10], # vertex(65, -10)
                    [cx + 65, cy + 10]  # vertex(65, 10)
                ], np.int32)
            elif j == 3:
                # 第四個形狀：四邊形
                points = np.array([
                    [cx + 10, cy + 13], # vertex(10, 13)
                    [cx + 65, cy + 20], # vertex(65, 20)
                    [cx + 65, cy + 35], # vertex(65, 35)
                    [cx + 30, cy + 35]  # vertex(30, 35)
                ], np.int32)
            elif j == 4:
                # 第五個形狀：三角形
                points = np.array([
                    [cx, cy + 10],      # vertex(0, 10)
                    [cx + 20, cy + 35], # vertex(20, 35)
                    [cx - 20, cy + 35]  # vertex(-20, 35)
                ], np.int32)
            elif j == 5:
                # 第六個形狀：四邊形
                points = np.array([
                    [cx - 10, cy + 13], # vertex(-10, 13)
                    [cx - 30, cy + 35], # vertex(-30, 35)
                    [cx - 65, cy + 35], # vertex(-65, 35)
                    [cx - 65, cy + 20]  # vertex(-65, 20)
                ], np.int32)
            elif j == 6:
                # 第七個形狀：三角形
                points = np.array([
                    [cx - 10, cy + 5],  # vertex(-10, 5)
                    [cx - 65, cy + 10], # vertex(-65, 10)
                    [cx - 65, cy - 10]  # vertex(-65, -10)
                ], np.int32)
            else:  # j == 7
                # 第八個形狀：四邊形
                points = np.array([
                    [cx - 10, cy - 3],  # vertex(-10, -3)
                    [cx - 65, cy - 20], # vertex(-65, -20)
                    [cx - 65, cy - 30], # vertex(-65, -30)
                    [cx - 30, cy - 30]  # vertex(-30, -30)
                ], np.int32)
            
            # 模擬 Processing 的 beginShape() 和 endShape(CLOSE)
            if fill_color:
                # 如果有填充顏色，先填充
                cv2.fillPoly(frame, [points], fill_color)
            # 然後畫邊框（模擬 stroke）
            cv2.polylines(frame, [points], True, color, 1)
    
    def draw_grid_pattern_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的網格模式
        for i in range(16):
            for j in range(3):
                # 使用與舊版本相同的 noise 計算
                temp_value = pde_noise((j * 16 + i), current_frame * 0.01)
                
                # 計算矩形位置和大小，模擬舊版本的計算方式
                # rect(-Window_Width*0.4+Window_Width*0.05*i, -Window_Height*0.3+Window_Height*0.23*j, Window_Width*0.05, Window_Height*0.2)
                window_width = self.width
                window_height = self.height
                
                rect_x = int(cx - window_width * 0.4 + window_width * 0.05 * i)
                rect_y = int(cy - window_height * 0.3 + window_height * 0.23 * j)
                rect_w = int(window_width * 0.05)
                rect_h = int(window_height * 0.2)
                
                # 模擬 Processing 的三種狀態
                if temp_value > 0.7:
                    # 模擬 noStroke(); fill(255, 100*Enter_Light);
                    fill_alpha = int(100 * self.alpha)
                    fill_color = tuple(int(c * fill_alpha / 255) for c in color)
                    cv2.rectangle(frame, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), fill_color, -1)
                elif temp_value > 0.6:
                    # 模擬 stroke(255, 100*Enter_Light); noFill();
                    cv2.rectangle(frame, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), color, 1)
                else:
                    # 模擬 noFill(); noStroke();
                    # 不繪製任何東西
                    pass
    
    def draw_oscilloscope_cv(self, frame, cx, cy, color, current_frame):
        for i in range(4):
            temp_value = pde_noise(i + 2, current_frame * 0.01)
            line_y = int(cy - 15 + i * 15)
            cv2.line(frame, (int(cx - 64), line_y), (int(cx + 64), line_y), color, 1)
            
            dot_x = int(cx - 64 + temp_value * 128)
            cv2.circle(frame, (dot_x, line_y), 2, color, -1)
    
    def draw_radar_pattern_cv(self, frame, cx, cy, color, current_frame):
        cv2.circle(frame, (cx, cy), 5, color, -1)
        cv2.line(frame, (int(cx - 64), cy), (int(cx + 64), cy), color, 1)
        
        for i in range(6):
            temp_value = pde_noise(i + 8, current_frame * 0.02)
            radius = 10 + i * 5
            start_angle = int(360 * temp_value)
            span_angle = 30 + i * 8
            
            cv2.ellipse(frame, (cx, cy), (radius, radius), 0, start_angle, start_angle + span_angle, color, 1)
    
    def draw_complex_shapes_cv(self, frame, cx, cy, color, current_frame):
        cv2.circle(frame, (cx, cy), 5, color, -1)
        
        for i in range(6):
            temp_value = pde_noise(i * 1.5 + 9, current_frame * 0.03)
            rotation = 360 * temp_value
            
            fill_noise = pde_noise(i + 108, current_frame * 0.07)
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
    
    def draw_crosshair_pattern_cv(self, frame, cx, cy, color, current_frame):
        temp_x1 = pde_noise(self.i + 110, current_frame * 0.013)
        temp_y1 = pde_noise(self.i + 111, current_frame * 0.012)
        temp_x2 = pde_noise(self.i + 112, current_frame * 0.014)
        temp_y2 = pde_noise(self.i + 113, current_frame * 0.015)
        
        # 第一組十字準星線 (TempX1, TempY1)
        line_y1 = int(cy + temp_y1 * 90 - 45)
        line_x1 = int(cx + temp_x1 * 160 - 80)
        cv2.line(frame, (int(cx - 72), line_y1), (int(cx + 72), line_y1), color, 1)
        cv2.line(frame, (line_x1, int(cy - 35)), (line_x1, int(cy + 40)), color, 1)
        
        # 第一組標記線 (灰色，100, 100*Enter_Light)
        mark_alpha = int(100 * self.alpha)
        mark_color = tuple(int(c * mark_alpha / 255) for c in (100, 100, 100))
        
        # 水平標記線
        for offset_x in [0.02, 0.05, -0.02, -0.05]:
            start_x = int(cx - 80 + (temp_x1 + offset_x) * 160)
            end_x = int(cx - 80 + (temp_x1 + (offset_x + 0.03 if offset_x > 0 else offset_x - 0.03)) * 160)
            mark_y = int(cy + (temp_y1 - 0.03) * 90 - 45)
            cv2.line(frame, (start_x, mark_y), (end_x, mark_y), mark_color, 1)
            
            mark_y = int(cy + (temp_y1 + 0.03) * 90 - 45)
            cv2.line(frame, (start_x, mark_y), (end_x, mark_y), mark_color, 1)
        
        # 垂直標記線
        for offset_x in [0.02, -0.02]:
            mark_x = int(cx - 80 + (temp_x1 + offset_x) * 160)
            start_y = int(cy + (temp_y1 - 0.03) * 90 - 45)
            end_y = int(cy + (temp_y1 - 0.07) * 90 - 45)
            cv2.line(frame, (mark_x, start_y), (mark_x, end_y), mark_color, 1)
            
            start_y = int(cy + (temp_y1 + 0.03) * 90 - 45)
            end_y = int(cy + (temp_y1 + 0.07) * 90 - 45)
            cv2.line(frame, (mark_x, start_y), (mark_x, end_y), mark_color, 1)
        
        # 第二組十字準星線 (TempX2, TempY2)
        line_y2 = int(cy + temp_y2 * 90 - 45)
        line_x2 = int(cx + temp_x2 * 160 - 80)
        cv2.line(frame, (int(cx - 72), line_y2), (int(cx + 72), line_y2), color, 1)
        cv2.line(frame, (line_x2, int(cy - 35)), (line_x2, int(cy + 40)), color, 1)
        
        # 第二組標記線 (灰色，100, 100*Enter_Light)
        # 水平標記線
        for offset_x in [0.02, 0.05, -0.02, -0.05]:
            start_x = int(cx - 80 + (temp_x2 + offset_x) * 160)
            end_x = int(cx - 80 + (temp_x2 + (offset_x + 0.03 if offset_x > 0 else offset_x - 0.03)) * 160)
            mark_y = int(cy + (temp_y2 - 0.03) * 90 - 45)
            cv2.line(frame, (start_x, mark_y), (end_x, mark_y), mark_color, 1)
            
            mark_y = int(cy + (temp_y2 + 0.03) * 90 - 45)
            cv2.line(frame, (start_x, mark_y), (end_x, mark_y), mark_color, 1)
        
        # 垂直標記線
        for offset_x in [0.02, -0.02]:
            mark_x = int(cx - 80 + (temp_x2 + offset_x) * 160)
            start_y = int(cy + (temp_y2 - 0.03) * 90 - 45)
            end_y = int(cy + (temp_y2 - 0.07) * 90 - 45)
            cv2.line(frame, (mark_x, start_y), (mark_x, end_y), mark_color, 1)
            
            start_y = int(cy + (temp_y2 + 0.03) * 90 - 45)
            end_y = int(cy + (temp_y2 + 0.07) * 90 - 45)
            cv2.line(frame, (mark_x, start_y), (mark_x, end_y), mark_color, 1)
    
    def draw_diamond_shapes_cv(self, frame, cx, cy, color, current_frame):
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
            fill_noise = pde_noise(self.i + 111 + i, current_frame * 0.021)
            points = np.array([[cx + x, cy + y] for x, y in shape_points], np.int32)
            
            if fill_noise > 0.5:
                fill_alpha = int(100 * self.alpha)
                fill_color = tuple(int(c * fill_alpha / 255) for c in (255, 255, 255))
                cv2.fillPoly(frame, [points], fill_color)
            cv2.polylines(frame, [points], True, color, 1)
    
    def draw_level_indicators_cv(self, frame, cx, cy, color, current_frame):
        temp_value = pde_noise(self.i + 13, current_frame * self.content_animation_speed) * 15 - 1
        
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
    
    def draw_progress_bars_cv(self, frame, cx, cy, color, current_frame):
        for i in range(4):
            temp_value = pde_noise(i + 1, current_frame * self.content_animation_speed)
            bar_y = int(cy - 25 + 15 * i)
            bar_h = 10
            
            filled_width = int(temp_value * 128) - 2
            cv2.rectangle(frame, (int(cx - 64), bar_y), 
                         (int(cx - 64) + filled_width, bar_y + bar_h), color, -1)
            
            empty_start = int(cx - 64) + filled_width + 3
            empty_width = 128 - filled_width - 3
            cv2.rectangle(frame, (empty_start, bar_y), (empty_start + empty_width, bar_y + bar_h), color, 1)
    
    def draw_vertical_oscilloscope_cv(self, frame, cx, cy, color, current_frame):
        for i in range(16):
            bar_x = int(cx - 70 + i * 9)
            noise_val = pde_noise(i, current_frame * self.content_animation_speed)
            
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 - 35 * noise_val)), color, 1)
            cv2.line(frame, (bar_x, int(cy + 5)), 
                     (bar_x, int(cy + 5 + 35 * noise_val)), color, 1)
    
    def draw_orbital_pattern_cv(self, frame, cx, cy, color, current_frame):
        # 模擬 Processing 版本的 Window 10: 十字準星模式
        # 計算兩個不同的 noise 值對
        temp_value_x1 = pde_noise(self.i + 110, current_frame * 0.013)
        temp_value_y1 = pde_noise(self.i + 111, current_frame * 0.012)
        temp_value_x2 = pde_noise(self.i + 112, current_frame * 0.014)
        temp_value_y2 = pde_noise(self.i + 113, current_frame * 0.015)
        
        # 計算窗口尺寸
        window_width = self.width
        window_height = self.height
        
        # 第一組十字準星 (TempX1, TempY1)
        # 水平線
        y1_pos = temp_value_y1 * window_height * 0.9 - window_height * 0.45
        cv2.line(frame, 
                 (int(cx - window_width * 0.45), int(cy + y1_pos)), 
                 (int(cx + window_width * 0.45), int(cy + y1_pos)), 
                 color, 1)
        
        # 垂直線
        x1_pos = temp_value_x1 * window_width - window_width * 0.5
        cv2.line(frame, 
                 (int(cx + x1_pos), int(cy - window_height * 0.35)), 
                 (int(cx + x1_pos), int(cy + window_height * 0.4)), 
                 color, 1)
        
        # 第一組十字準星的輔助線 (灰色)
        gray_color = tuple(int(c * 0.4) for c in color)  # 模擬 stroke(100, 100*Enter_Light)
        
        # 水平輔助線
        for offset_x in [0.02, -0.02]:
            for offset_y in [0.03, -0.03]:
                x_start = x1_pos + offset_x * window_width
                x_end = x1_pos + (offset_x + 0.03) * window_width
                y_pos = y1_pos + offset_y * window_height * 0.9
                
                cv2.line(frame, 
                         (int(cx + x_start), int(cy + y_pos)), 
                         (int(cx + x_end), int(cy + y_pos)), 
                         gray_color, 1)
        
        # 垂直輔助線
        for offset_x in [0.02, -0.02]:
            for offset_y in [0.03, -0.03]:
                x_pos = x1_pos + offset_x * window_width
                y_start = y1_pos + offset_y * window_height * 0.9
                y_end = y1_pos + (offset_y + 0.04) * window_height * 0.9
                
                cv2.line(frame, 
                         (int(cx + x_pos), int(cy + y_start)), 
                         (int(cx + x_pos), int(cy + y_end)), 
                         gray_color, 1)
        
        # 第二組十字準星 (TempX2, TempY2)
        # 水平線
        y2_pos = temp_value_y2 * window_height * 0.9 - window_height * 0.45
        cv2.line(frame, 
                 (int(cx - window_width * 0.45), int(cy + y2_pos)), 
                 (int(cx + window_width * 0.45), int(cy + y2_pos)), 
                 color, 1)
        
        # 垂直線
        x2_pos = temp_value_x2 * window_width - window_width * 0.5
        cv2.line(frame, 
                 (int(cx + x2_pos), int(cy - window_height * 0.35)), 
                 (int(cx + x2_pos), int(cy + window_height * 0.4)), 
                 color, 1)
        
        # 第二組十字準星的輔助線 (灰色)
        for offset_x in [0.02, -0.02]:
            for offset_y in [0.03, -0.03]:
                x_start = x2_pos + offset_x * window_width
                x_end = x2_pos + (offset_x + 0.03) * window_width
                y_pos = y2_pos + offset_y * window_height * 0.9
                
                cv2.line(frame, 
                         (int(cx + x_start), int(cy + y_pos)), 
                         (int(cx + x_end), int(cy + y_pos)), 
                         gray_color, 1)
        
        for offset_x in [0.02, -0.02]:
            for offset_y in [0.03, -0.03]:
                x_pos = x2_pos + offset_x * window_width
                y_start = y2_pos + offset_y * window_height * 0.9
                y_end = y2_pos + (offset_y + 0.04) * window_height * 0.9
                
                cv2.line(frame, 
                         (int(cx + x_pos), int(cy + y_start)), 
                         (int(cx + x_pos), int(cy + y_end)), 
                         gray_color, 1)
    
    def draw_stacked_bars_cv(self, frame, cx, cy, color, current_frame):
        temp_values = [
            pde_noise(self.i + 215, current_frame * self.content_animation_speed),
            pde_noise(self.i + 216, current_frame * self.content_animation_speed),
            pde_noise(self.i + 217, current_frame * self.content_animation_speed)
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

# 改進的窗口效果管理器
class ImprovedDetectionWindowEffect:
    def __init__(self, screen_width=1080, screen_height=1920, config=None):
        self.config = config or AnimConfigLoader()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.windows_by_face = {}
        self.center_points_by_face = {}
        
        # 從配置獲取生成參數
        self.spawn_rate = self.config.get_float('BASIC', 'spawn_rate', 0.1)
        self.max_windows_per_face = self.config.get_int('BASIC', 'max_windows_per_face', 4)
        self.spawn_delay_frames = self.config.get_int('BASIC', 'spawn_delay_frames', 30)
        
        self.face_states = {}
        self.window_spawn_delays = {}
        
        self.window_type_counters = {}
        self.window_type_sequences = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, 16]
        ]
        
        self.used_points_by_face = {}
        # 追蹤每個臉部已使用的窗口類型，避免重複
        self.used_window_types_by_face = {}
        
        # 消失效果相關
        self.fade_state = "normal"  # normal, fading, hidden
        self.fade_alpha = 1.0
        self.fade_start_time = None
        
    def update_faces(self, faces, face_states=None):
        current_face_ids = set(range(len(faces)))
        
        # 清理不存在的臉部
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
                if face_id in self.used_window_types_by_face:
                    del self.used_window_types_by_face[face_id]
        
        # 更新臉部狀態
        if face_states:
            for face_id, state in face_states.items():
                if face_id in current_face_ids:
                    old_state = self.face_states.get(face_id, 0)
                    self.face_states[face_id] = state
                    
                    if state == 3 and old_state < 3:
                        self.window_spawn_delays[face_id] = 0
                        self.window_type_counters[face_id] = 0
        
        # 處理每個臉部
        for i, (x, y, w, h) in enumerate(faces):
            center_x = x + w // 2
            center_y = y + h // 2
            face_size = max(w, h)
            
            if i not in self.windows_by_face:
                self.windows_by_face[i] = []
                self.generate_center_points_for_face(i, center_x, center_y, face_size)
                self.window_type_counters[i] = 0
                self.used_points_by_face[i] = []
                self.used_window_types_by_face[i] = []
            
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
        """更新點的位置，讓它們平滑跟隨人臉移動"""
        if face_id not in self.center_points_by_face:
            return
            
        # 獲取平滑移動參數
        smooth_factor = self.config.get_float('POSITION', 'point_smooth_factor', 0.1)
        
        # 重新生成點的位置，保持相對於檢測框的位置
        frame_size = face_size * 1.3
        frame_half_size = frame_size * 0.5
        
        # 從配置獲取象限擴散比例
        quadrant_spread = self.config.get_float('POSITION', 'quadrant_spread', 0.35)
        random_offset_ratio = self.config.get_float('POSITION', 'random_offset_ratio', 0.05)
        
        # 定義四個象限的偏移比例
        quadrant_offsets = [
            (-quadrant_spread, -quadrant_spread),  # 左上
            (quadrant_spread, -quadrant_spread),   # 右上
            (quadrant_spread, quadrant_spread),    # 右下
            (-quadrant_spread, quadrant_spread)    # 左下
        ]
        
        # 如果這是第一次生成點，直接設置位置
        if face_id not in self.center_points_by_face or not self.center_points_by_face[face_id]:
            updated_points = []
            for i, (offset_x, offset_y) in enumerate(quadrant_offsets):
                # 基於檢測框中心和大小計算點的位置
                point_x = center_x + frame_half_size * offset_x
                point_y = center_y + frame_half_size * offset_y
                
                # 加入小的隨機偏移
                point_x += random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
                point_y += random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
                
                # 確保在屏幕範圍內
                point_x = max(150, min(self.screen_width - 150, point_x))
                point_y = max(150, min(self.screen_height - 150, point_y))
                
                updated_points.append((int(point_x), int(point_y)))
            
            self.center_points_by_face[face_id] = updated_points
        else:
            # 平滑移動現有的點
            updated_points = []
            for i, (offset_x, offset_y) in enumerate(quadrant_offsets):
                # 計算目標位置
                target_x = center_x + frame_half_size * offset_x
                target_y = center_y + frame_half_size * offset_y
                
                # 加入小的隨機偏移
                target_x += random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
                target_y += random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
                
                # 確保在屏幕範圍內
                target_x = max(150, min(self.screen_width - 150, target_x))
                target_y = max(150, min(self.screen_height - 150, target_y))
                
                # 獲取當前點位置
                current_point = self.center_points_by_face[face_id][i]
                current_x, current_y = current_point
                
                # 平滑移動到目標位置
                new_x = current_x + (target_x - current_x) * smooth_factor
                new_y = current_y + (target_y - current_y) * smooth_factor
                
                updated_points.append((int(new_x), int(new_y)))
            
            self.center_points_by_face[face_id] = updated_points
        
        # 更新現有窗口的連接點
        for i, window in enumerate(self.windows_by_face[face_id]):
            # 找到窗口對應的點索引
            for idx, point in enumerate(updated_points):
                if idx in self.used_points_by_face[face_id]:
                    # 檢查這個點是否是當前窗口的連接點
                    old_point = self.center_points_by_face[face_id][idx] if idx < len(self.center_points_by_face[face_id]) else None
                    if old_point and hasattr(window, 'point_index') and window.point_index == idx:
                        # 讓窗口自己更新生成點位置（通過 update_center 方法）
                        pass
    
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
            available_points = list(range(4))
        
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
        
        new_window = ImprovedCalWindow(win_x, win_y, face_size, window_type, self.config)
        new_window.x = win_x
        new_window.y = win_y
        new_window.spawn_center_x = spawn_center[0]
        new_window.spawn_center_y = spawn_center[1]
        # 設置固定的生成點，避免連接線抖動
        new_window.fixed_spawn_center_x = spawn_center[0]
        new_window.fixed_spawn_center_y = spawn_center[1]
        new_window.point_index = point_index  # 記錄使用的點索引
        new_window.face_size = face_size  # 記錄臉部大小，用於重新計算生成點
        new_window.update_position()
        
        self.windows_by_face[face_id].append(new_window)
        
        # 重置延遲計時器
        if face_id in self.window_spawn_delays:
            self.window_spawn_delays[face_id] = -45
    
    def _get_next_window_type(self, face_id):
        # 獲取已使用的窗口類型
        used_types = self.used_window_types_by_face.get(face_id, [])
        
        # 如果已經使用了所有16種類型，重置列表
        if len(used_types) >= 16:
            self.used_window_types_by_face[face_id] = []
            used_types = []
        
        # 創建可用的窗口類型列表（排除已使用的）
        available_types = [i for i in range(1, 17) if i not in used_types]
        
        # 隨機選擇一個未使用的類型
        if available_types:
            window_type = random.choice(available_types)
            # 添加到已使用列表
            self.used_window_types_by_face[face_id].append(window_type)
            return window_type
        else:
            # 如果沒有可用的類型（理論上不會發生），返回隨機類型
            return random.randint(1, 16)
    
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
        """生成4個分散在四個角落的點"""
        center_points = []
        
        frame_size = face_size * 1.3
        frame_half_size = frame_size * 0.5
        
        # 從配置獲取象限擴散比例
        quadrant_spread = self.config.get_float('POSITION', 'quadrant_spread', 0.35)
        random_offset_ratio = self.config.get_float('POSITION', 'random_offset_ratio', 0.05)
        
        # 固定的四個象限偏移
        quadrant_offsets = [
            (-quadrant_spread, -quadrant_spread),  # 左上
            (quadrant_spread, -quadrant_spread),   # 右上
            (quadrant_spread, quadrant_spread),    # 右下
            (-quadrant_spread, quadrant_spread)    # 左下
        ]
        
        for offset_x, offset_y in quadrant_offsets:
            # 基礎位置
            base_x = center_x + frame_half_size * offset_x
            base_y = center_y + frame_half_size * offset_y
            
            # 加入小的隨機偏移
            x = base_x + random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
            y = base_y + random.uniform(-face_size * random_offset_ratio, face_size * random_offset_ratio)
            
            # 確保在屏幕範圍內
            x = max(150, min(self.screen_width - 150, x))
            y = max(150, min(self.screen_height - 150, y))
            
            center_points.append((int(x), int(y)))
        
        self.center_points_by_face[face_id] = center_points
    
    def _generate_window_position_in_quadrant(self, center_x, center_y, face_size, quadrant_index):
        """在對應象限生成窗口位置"""
        # 從配置獲取距離參數
        min_radius = self.config.get_int('POSITION', 'min_radius', 200)
        max_radius = self.config.get_int('POSITION', 'max_radius', 350)
        
        base_distance = face_size * 1.5
        
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
        
        distance = base_distance + random.uniform(0, face_size * 0.3)
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
        # 如果正在消失，調整透明度
        if self.fade_state == "fading":
            # 計算消失進度
            if self.fade_start_time:
                elapsed = time.time() - self.fade_start_time
                fade_duration = 0.5  # 0.5秒消失時間
                self.fade_alpha = max(0.0, 1.0 - (elapsed / fade_duration))
                
                if self.fade_alpha <= 0.0:
                    self.fade_state = "hidden"
                    self.fade_alpha = 0.0
        
        # 如果已隱藏，不繪製
        if self.fade_state == "hidden":
            return
            
        for face_id, windows in self.windows_by_face.items():
            for window in windows:
                if face_id in self.face_states:
                    window.set_detection_state(self.face_states[face_id])
                # 應用消失透明度
                window.alpha = self.fade_alpha
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
        self.used_window_types_by_face.clear()
        
    def start_fade_out(self):
        """開始消失效果"""
        print("🎭 Cal Windows 開始消失效果")
        self.fade_state = "fading"
        self.fade_start_time = time.time()
        self.fade_alpha = 1.0
        
    def reset_fade_state(self):
        """重置消失狀態"""
        self.fade_state = "normal"
        self.fade_alpha = 1.0
        self.fade_start_time = None 