# Location: project_v2/ui/cal_windows_effect.py

# Usage: 科技感窗口動畫效果模組 - 適配檢測框中心點系統

import random
import math
import cv2
import numpy as np

# ===== 配置參數 =====
# 視窗生成
SPAWN_RATE = 0.25  # 每幀生成視窗的機率 (增加生成率)
MIN_LIFE = 80      # 視窗最小生命值 (縮短生命週期，讓更多窗口並存)
MAX_LIFE = 150     # 視窗最大生命值 (縮短生命週期)
LIFE_DECAY = 1     # 每幀生命值衰減

# 獨立模式配置 (LLM載入時使用)
STANDALONE_SPAWN_RATE = 0.3    # 獨立模式的生成率更高
STANDALONE_CENTER_COUNT = 2    # 獨立模式的中心點數量
STANDALONE_CENTER_SPREAD = 200 # 獨立模式的中心點擴散範圍

# 視窗大小 (16:9 比例，*2倍大小)
WINDOW_WIDTH_DEFAULT = 160   # 預設寬度 (*2)
WINDOW_HEIGHT_DEFAULT = 100   # 預設高度 (*2)

# 視窗位置 (相對於檢測框)
MIN_RADIUS = 150   # 最小距離中心點距離
MAX_RADIUS = 250   # 最大距離中心點距離
MAX_PHI = 20       # 最大垂直角度

# 中心點配置 (每個檢測框)
CENTER_POINTS_PER_FACE = 4    # 每個檢測框的中心點數量
CENTER_SPREAD = 80            # 中心點擴散範圍 (相對於檢測框大小)

# 視窗類型
WINDOW_TYPES = 16   # 視窗內容類型數量

# ===== 動畫速度配置 =====
ANIMATION_SPEED_MULTIPLIER = 1.0   
CONTENT_ANIMATION_SPEED = 0.1      
TIME_SCALE = 0.1                   

# 全域frame_count變數
frame_count = 0

# Processing風格的噪聲實現
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
            random.seed(seed)
            return random.random()
        
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

# 建立全域 noise 物件
perlin = ProcessingStyleNoise()

def pde_noise(x, y=0, z=0):
    """模擬Processing的noise函數"""
    return perlin.noise(x, y, z)


class CalWindowForDetection:
    """適配檢測框的科技窗口類 - 使用修復後的版本"""
    
    def __init__(self, center_x, center_y, face_size):
        self.center_x = center_x
        self.center_y = center_y
        self.face_size = face_size
        
        # 視窗屬性 - 使用固定的160x100尺寸
        self.width = 160  # 原始 WINDOW_WIDTH_DEFAULT
        self.height = 100  # 原始 WINDOW_HEIGHT_DEFAULT
        self.window_kind = random.randint(1, WINDOW_TYPES)
        self.life = random.randint(MIN_LIFE, MAX_LIFE)
        self.max_life = self.life
        self.display = True
        
        # 極座標位置 - 確保在檢測框外但可見範圍內
        min_radius = max(face_size * 1.5, 200)  # 至少距離檢測框1.5倍大小
        screen_distance = min(center_x, center_y, 1080-center_x, 1920-center_y)
        max_radius = max(min_radius + 100, min(400, screen_distance * 0.9))
        self.r = random.uniform(min_radius, max_radius)
        self.theta = random.uniform(0, 360)
        self.phi = random.uniform(-MAX_PHI, MAX_PHI)
        
        # 計算笛卡爾座標位置
        self.update_position()
        
        # 動畫屬性
        self.i = random.randint(0, 1000)
        self.alpha = 1.0
        self.mode = 3
        
        # 連接線偏移 - 使用固定值
        self.connection_offset_x = random.uniform(-40, 40)
        self.connection_offset_y = random.uniform(-25, 25)
        self.quadrant = random.randint(0, 3)
        
        # 強制閃爍狀態
        self.force_flicker = False
        
    def update_position(self):
        """更新窗口位置 - 基於生成點計算位置"""
        try:
            rad_theta = math.radians(self.theta)
            rad_phi = math.radians(self.phi)
            
            # 基於中心點計算窗口位置
            self.x = self.center_x + self.r * math.cos(rad_theta) * math.cos(rad_phi)
            self.y = self.center_y + self.r * math.sin(rad_theta) * math.cos(rad_phi)
            
            # 確保窗口在屏幕範圍內
            self.x = max(self.width//2, min(1080 - self.width//2, self.x))
            self.y = max(self.height//2, min(1920 - self.height//2, self.y))
            
            # 額外檢查：確保窗口不會與檢測框重疊
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
        except Exception as e:
            print(f"窗口位置更新錯誤: {e}")
            # 使用安全的默認值
            self.x = 540  # 屏幕中心
            self.y = 960
    
    def set_force_flicker(self, should_flicker):
        """設置強制閃爍狀態（與檢測框同步）"""
        self.force_flicker = should_flicker
        
    def update(self):
        global frame_count
        
        self.life -= LIFE_DECAY
        
        # 更新模式
        if self.life >= self.max_life * 0.8:
            self.mode = 3
        elif self.life >= self.max_life * 0.2:
            self.mode = 2
        elif self.life > 0:
            self.mode = 1
        else:
            self.mode = 0
            
        # 根據模式和強制閃爍更新顯示狀態
        if self.force_flicker:
            # 強制閃爍時優先使用強制狀態
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
        """在OpenCV幀上繪製窗口"""
        if not self.display:
            return
            
        alpha_int = int(255 * self.alpha)
        
        # 繪製連接線
        connection_alpha = int(50 * self.alpha)
        connection_color = tuple(int(c * connection_alpha / 255) for c in color_bgr)
        
        cv2.line(frame, 
                (int(self.x), int(self.y)), 
                (int(self.x - self.connection_offset_x), int(self.y - self.connection_offset_y)), 
                connection_color, 1)
        cv2.line(frame, 
                (int(self.x - self.connection_offset_x), int(self.y - self.connection_offset_y)), 
                (int(self.center_x), int(self.center_y)), 
                connection_color, 1)
        
        # 繪製視窗框架
        frame_alpha = int(100 * self.alpha)
        frame_color = tuple(int(c * frame_alpha / 255) for c in color_bgr)
        
        # 主視窗框架
        wx = int(self.x - self.width/2)
        wy = int(self.y - self.height/2)
        cv2.rectangle(frame, (wx, wy), (wx + self.width, wy + self.height), frame_color, 1)
        
        # 內框
        inner_x = int(self.x - self.width * 0.46)
        inner_y = int(self.y - self.height * 0.4)
        inner_w = int(self.width * 0.92)
        inner_h = int(self.height * 0.8)
        cv2.rectangle(frame, (inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h), frame_color, 1)
        
        # 標題欄按鈕
        cv2.rectangle(frame, (wx + 6, wy + 3), (wx + 12, wy + 9), frame_color, 1)
        cv2.rectangle(frame, (wx + 20, wy + 3), (wx + 26, wy + 9), frame_color, 1)
        
        # 繪製內容
        self.draw_content_on_cv(frame, self.x, self.y, frame_color)
    
    def draw_content_on_cv(self, frame, cx, cy, color):
        """在OpenCV幀上繪製視窗內容"""
        content_alpha = int(100 * self.alpha)
        content_color = tuple(int(c * content_alpha / 255) for c in color)
        
        if self.window_kind == 1:      # Bar chart
            self.draw_bar_chart_cv(frame, cx, cy, content_color)
        elif self.window_kind == 2:    # Line chart with points
            self.draw_line_chart_cv(frame, cx, cy, content_color)
        elif self.window_kind == 3:    # Curve chart
            self.draw_curve_chart_cv(frame, cx, cy, content_color)
        elif self.window_kind == 4:    # Matrix display
            self.draw_matrix_display_cv(frame, cx, cy, content_color)
        elif self.window_kind == 5:    # Geometric pattern
            self.draw_geometric_pattern_cv(frame, cx, cy, content_color)
        elif self.window_kind == 6:    # Grid pattern
            self.draw_grid_pattern_cv(frame, cx, cy, content_color)
        elif self.window_kind == 7:    # Oscilloscope
            self.draw_oscilloscope_cv(frame, cx, cy, content_color)
        elif self.window_kind == 8:    # Radar pattern
            self.draw_radar_pattern_cv(frame, cx, cy, content_color)
        elif self.window_kind == 9:    # Complex shapes
            self.draw_complex_shapes_cv(frame, cx, cy, content_color)
        elif self.window_kind == 10:   # Crosshair pattern
            self.draw_crosshair_pattern_cv(frame, cx, cy, content_color)
        elif self.window_kind == 11:   # Diamond shapes
            self.draw_diamond_shapes_cv(frame, cx, cy, content_color)
        elif self.window_kind == 12:   # Level indicators
            self.draw_level_indicators_cv(frame, cx, cy, content_color)
        elif self.window_kind == 13:   # Progress bars
            self.draw_progress_bars_cv(frame, cx, cy, content_color)
        elif self.window_kind == 14:   # Vertical oscilloscope
            self.draw_vertical_oscilloscope_cv(frame, cx, cy, content_color)
        elif self.window_kind == 15:   # Orbital pattern
            self.draw_orbital_pattern_cv(frame, cx, cy, content_color)
        elif self.window_kind == 16:   # Stacked bars
            self.draw_stacked_bars_cv(frame, cx, cy, content_color)
    
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
        """繪製幾何圖案到OpenCV幀"""
        for j in range(8):
            fill_noise = pde_noise(self.i + j, frame_count * CONTENT_ANIMATION_SPEED)
            
            # 根據noise決定是否填充
            thickness = -1 if fill_noise > 0.5 else 1
            
            # 繪製不同的三角形（簡化為矩形）
            if j == 0:  # 中心
                pts = np.array([[int(cx), int(cy - 30)], [int(cx - 20), int(cy)], [int(cx + 20), int(cy)]], np.int32)
            elif j == 1:  # 右上
                pts = np.array([[int(cx + 10), int(cy - 15)], [int(cx + 30), int(cy - 30)], [int(cx + 50), int(cy - 10)]], np.int32)
            else:
                # 其他形狀的簡化實現
                pts = np.array([[int(cx + j*10), int(cy)], [int(cx + j*10 + 15), int(cy - 15)], [int(cx + j*10 + 15), int(cy + 15)]], np.int32)
            
            cv2.fillPoly(frame, [pts], color) if thickness == -1 else cv2.polylines(frame, [pts], True, color, 1)
    
    def draw_grid_pattern_cv(self, frame, cx, cy, color):
        """繪製網格圖案到OpenCV幀"""
        for i in range(16):
            for j in range(3):
                temp_value = pde_noise((j * 16 + i), frame_count * 0.01)
                px = int(cx - self.width * 0.4 + self.width * 0.05 * i)
                py = int(cy - self.height * 0.3 + self.height * 0.23 * j)
                cell_w = int(self.width * 0.05)
                cell_h = int(self.height * 0.2)
                
                if temp_value > 0.7:
                    cv2.rectangle(frame, (px, py), (px + cell_w, py + cell_h), color, -1)
                elif temp_value > 0.6:
                    cv2.rectangle(frame, (px, py), (px + cell_w, py + cell_h), color, 1)
    
    def draw_oscilloscope_cv(self, frame, cx, cy, color):
        """繪製示波器到OpenCV幀"""
        for i in range(4):
            temp_value = pde_noise(i + 2, frame_count * 0.01)
            line_y = int(cy - self.height * 0.15 + i * 0.15 * self.height)
            cv2.line(frame, (int(cx - self.width * 0.4), line_y), (int(cx + self.width * 0.4), line_y), color, 1)
            
            # 動態點
            dot_x = int(cx - self.width * 0.4 + temp_value * self.width * 0.8)
            cv2.circle(frame, (dot_x, line_y), 2, color, -1)
    
    def draw_radar_pattern_cv(self, frame, cx, cy, color):
        """繪製雷達圖案到OpenCV幀"""
        cv2.circle(frame, (int(cx), int(cy)), 5, color, 1)
        cv2.line(frame, (int(cx - self.width * 0.4), int(cy)), (int(cx + self.width * 0.4), int(cy)), color, 1)
        
        for i in range(6):
            temp_value = pde_noise(i + 8, frame_count * 0.02)
            radius = 10 + i * 5
            start_angle = int(360 * temp_value)
            end_angle = start_angle + 30 + i * 8
            # OpenCV的弧線繪製需要特殊處理，這裡簡化為圓
            cv2.circle(frame, (int(cx), int(cy)), radius, color, 1)
    
    def draw_complex_shapes_cv(self, frame, cx, cy, color):
        """繪製複雜形狀到OpenCV幀"""
        cv2.circle(frame, (int(cx), int(cy)), 5, color, 1)
        
        for i in range(6):
            temp_value = pde_noise(i * 1.5 + 9, frame_count * 0.03)
            angle = 360 * temp_value
            
            # 簡化的旋轉形狀
            for j in range(i*2+4):
                angle_rad = math.radians(j * 15 + angle)
                x1 = int(cx + i*3 * math.cos(angle_rad))
                y1 = int(cy + i*3 * math.sin(angle_rad))
                x2 = int(cx + (i+1)*3 * math.cos(angle_rad))
                y2 = int(cy + (i+1)*3 * math.sin(angle_rad))
                cv2.line(frame, (x1, y1), (x2, y2), color, 1)
    
    def draw_crosshair_pattern_cv(self, frame, cx, cy, color):
        """繪製十字準星圖案到OpenCV幀"""
        temp_x1 = pde_noise(self.i + 110, frame_count * 0.013)
        temp_y1 = pde_noise(self.i + 111, frame_count * 0.012)
        
        # 十字線
        line_y = int(temp_y1 * self.height * 0.9 + cy - self.height * 0.45)
        line_x = int(temp_x1 * self.width + cx - self.width * 0.5)
        cv2.line(frame, (int(cx - self.width * 0.45), line_y), (int(cx + self.width * 0.45), line_y), color, 1)
        cv2.line(frame, (line_x, int(cy - self.height * 0.35)), (line_x, int(cy + self.height * 0.4)), color, 1)
    
    def draw_diamond_shapes_cv(self, frame, cx, cy, color):
        """繪製鑽石形狀到OpenCV幀"""
        # 中心鑽石
        pts = np.array([
            [int(cx), int(cy - self.height * 0.3)],
            [int(cx + self.width * 0.1), int(cy + self.height * 0.025)],
            [int(cx), int(cy + self.height * 0.35)],
            [int(cx - self.width * 0.1), int(cy + self.height * 0.025)]
        ], np.int32)
        
        fill_noise = pde_noise(self.i + 111, frame_count * 0.021)
        if fill_noise > 0.5:
            cv2.fillPoly(frame, [pts], color)
        else:
            cv2.polylines(frame, [pts], True, color, 1)
        
        # 其他小形狀
        for i in range(4):
            fill_noise = pde_noise(self.i + 112 + i, frame_count * 0.021)
            angle = i * 90
            rad = math.radians(angle)
            offset_x = int(self.width * 0.25 * math.cos(rad))
            offset_y = int(self.height * 0.25 * math.sin(rad))
            
            small_pts = np.array([
                [int(cx + offset_x), int(cy + offset_y - 10)],
                [int(cx + offset_x + 8), int(cy + offset_y)],
                [int(cx + offset_x), int(cy + offset_y + 10)],
                [int(cx + offset_x - 8), int(cy + offset_y)]
            ], np.int32)
            
            if fill_noise > 0.5:
                cv2.fillPoly(frame, [small_pts], color)
            else:
                cv2.polylines(frame, [small_pts], True, color, 1)
    
    def draw_level_indicators_cv(self, frame, cx, cy, color):
        """繪製等級指示器到OpenCV幀"""
        temp_value = pde_noise(self.i + 13, frame_count * 0.1)
        temp_value = temp_value * 15 - 1
        
        # 垂直等級條
        for i in range(13):
            bar_y = int(cy + self.height * 0.35 - self.height * 0.05 * i)
            bar_h = int(self.height * 0.05)
            bar_x = int(cx - self.width * 0.05)
            bar_w = int(self.width * 0.1)
            
            if i <= temp_value:
                cv2.rectangle(frame, (bar_x, bar_y - bar_h), (bar_x + bar_w, bar_y), color, -1)
            else:
                cv2.rectangle(frame, (bar_x, bar_y - bar_h), (bar_x + bar_w, bar_y), color, 1)
        
        # 側邊標記點
        for i in range(0, 13, 2):
            mark_y = int(cy + self.height * 0.35 - self.height * 0.05 * i)
            cv2.circle(frame, (int(cx - self.width * 0.1), mark_y), 2, color, -1)
            cv2.circle(frame, (int(cx + self.width * 0.1), mark_y), 2, color, -1)
        
        # 圓形圖案
        for i, offset_x in enumerate([-self.width * 0.3, self.width * 0.3]):
            center_x = int(cx + offset_x)
            center_y = int(cy - self.height * 0.15)
            temp_val = pde_noise(self.i + 113 + i, frame_count * 0.1)
            
            cv2.circle(frame, (center_x, center_y), 5, color, 1)
            cv2.circle(frame, (center_x, center_y), 10, color, 1)
            cv2.circle(frame, (center_x, center_y), 15, color, 1)
    
    def draw_progress_bars_cv(self, frame, cx, cy, color):
        """繪製進度條到OpenCV幀"""
        for i in range(4):
            temp_value = pde_noise(i + 1, frame_count * 0.1)
            bar_y = int(cy - self.height * (0.25 - 0.15 * i))
            bar_h = int(self.height * 0.1)
            
            # 填充部分
            filled_width = int(temp_value * self.width * 0.8) - 2
            bar_x = int(cx - self.width * 0.4)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_width, bar_y + bar_h), color, -1)
            
            # 空白部分
            empty_start = bar_x + filled_width + 3
            empty_width = int(self.width * 0.8) - filled_width - 3
            if empty_width > 0:
                cv2.rectangle(frame, (empty_start, bar_y), (empty_start + empty_width, bar_y + bar_h), color, 1)
    
    def draw_vertical_oscilloscope_cv(self, frame, cx, cy, color):
        """繪製垂直示波器到OpenCV幀"""
        for i in range(16):
            bar_x = int(cx - 70 + i * 9)
            noise_val = pde_noise(i, frame_count * 0.1)
            
            # 向上的線
            cv2.line(frame, (bar_x, int(cy + 5)), (bar_x, int(cy + 5 - 35 * noise_val)), color, 1)
            # 向下的線
            cv2.line(frame, (bar_x, int(cy + 5)), (bar_x, int(cy + 5 + 35 * noise_val)), color, 1)
    
    def draw_orbital_pattern_cv(self, frame, cx, cy, color):
        """繪製軌道圖案到OpenCV幀"""
        temp_values = [
            pde_noise(self.i + 215, frame_count * 0.1),
            pde_noise(self.i + 216, frame_count * 0.1),
            pde_noise(self.i + 217, frame_count * 0.1)
        ]
        
        center_x = int(cx - self.width * 0.15)
        center_y = int(cy + self.height * 0.05)
        
        # 三個同心圓
        radii = [int(self.width * 0.05), int(self.width * 0.125), int(self.width * 0.2)]
        for radius in radii:
            cv2.circle(frame, (center_x, center_y), radius, color, 1)
        
        # 基準點
        base_x = int(cx - self.width * 0.05)
        base_y = int(cy + self.height * 0.05)
        
        # 軌道線和軌道點
        for i, (radius, temp_val) in enumerate(zip(radii, temp_values)):
            angle_rad = math.radians(temp_val * 360)
            orbit_x = int(radius * math.cos(angle_rad)) + center_x
            orbit_y = int(radius * math.sin(angle_rad)) + center_y
            
            # 連接線
            cv2.line(frame, (base_x, base_y), (orbit_x, orbit_y), color, 1)
            
            # 軌道點
            point_r = int(self.width * 0.025)
            cv2.circle(frame, (orbit_x, orbit_y), point_r, color, 1)
    
    def draw_stacked_bars_cv(self, frame, cx, cy, color):
        """繪製堆疊條形圖到OpenCV幀"""
        temp_values = [
            pde_noise(self.i + 215, frame_count * 0.1),
            pde_noise(self.i + 216, frame_count * 0.1),
            pde_noise(self.i + 217, frame_count * 0.1)
        ]
        
        # 水平網格線
        for i in range(14):
            line_y = int(cy - self.height * (0.3 - i * 0.05))
            cv2.line(frame, (int(cx - self.width * 0.4), line_y), (int(cx + self.width * 0.4), line_y), color, 1)
        
        # 三個堆疊條
        bar_positions = [-0.25, -0.05, 0.15]
        for i, (pos, temp_val) in enumerate(zip(bar_positions, temp_values)):
            bar_height = int(temp_val * self.height * 0.9)
            bar_x = int(cx + self.width * pos)
            bar_y = int(cy + self.height * 0.4)
            bar_w = int(self.width * 0.1)
            
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y - bar_height), color, -1)


class DetectionWindowEffect:
    """檢測框窗口效果管理器"""
    
    def __init__(self, screen_width=1280, screen_height=720):
        self.windows_by_face = {}  # 每個人臉對應的窗口列表
        self.center_points_by_face = {}  # 每個人臉對應的中心點
        
        # 獨立模式相關
        self.standalone_mode = False
        self.standalone_windows = []  # 獨立模式的窗口列表
        self.standalone_center_points = []  # 獨立模式的中心點
        self.screen_width = screen_width
        self.screen_height = screen_height
        
    def update_faces(self, faces):
        """更新人臉檢測結果 - 使用修復後的邏輯"""
        current_face_ids = set(range(len(faces)))
        
        # 清理不存在的人臉
        for face_id in list(self.windows_by_face.keys()):
            if face_id not in current_face_ids:
                del self.windows_by_face[face_id]
                if face_id in self.center_points_by_face:
                    del self.center_points_by_face[face_id]
        
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
                window.center_x = center_x
                window.center_y = center_y
                window.face_size = face_size
                window.update_position()
            
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
            
            # 生成新窗口 - 從隨機中心點生成
            if len(self.windows_by_face[i]) < 4 and random.random() < SPAWN_RATE:
                if i in self.center_points_by_face and self.center_points_by_face[i]:
                    # 從隨機中心點生成窗口，但確保每個窗口使用不同的生成點
                    available_spawn_points = self.center_points_by_face[i].copy()
                    
                    # 移除已經被使用的生成點
                    for window in self.windows_by_face[i]:
                        for point in available_spawn_points[:]:
                            if abs(point[0] - window.center_x) < 10 and abs(point[1] - window.center_y) < 10:
                                available_spawn_points.remove(point)
                                break
                    
                    # 如果有可用的生成點，創建新窗口
                    if available_spawn_points:
                        spawn_center = random.choice(available_spawn_points)
                        new_window = CalWindowForDetection(spawn_center[0], spawn_center[1], face_size)
                        self.windows_by_face[i].append(new_window)
            
            # 更新現有窗口並移除已死亡的
            self.windows_by_face[i] = [w for w in self.windows_by_face[i] if w.update()]
    
    def generate_center_points_for_face(self, face_id, center_x, center_y, face_size):
        """為人臉生成4個隨機中心點 - 使用修復後的邏輯"""
        center_points = []
        
        # 參考原始代碼的邏輯，生成4個中心點
        base_x, base_y = center_x, center_y
        
        for i in range(4):
            if i == 0:
                # 第一個點：在中心附近隨機
                x = base_x + random.randint(-30, 30)
                y = base_y + random.randint(-30, 30)
            else:
                # 其他點：在90度角度上隨機分布
                angle = (i * 360 / 4) + random.randint(-20, 20)  # 90度間隔 + 隨機偏移
                distance = 120 + random.randint(-30, 30)  # CENTER_SPREAD + 隨機距離
                rad = math.radians(angle)
                x = base_x + distance * math.cos(rad)
                y = base_y + distance * math.sin(rad)
            
            # 確保點在屏幕範圍內
            x = max(100, min(1080 - 100, x))
            y = max(100, min(1920 - 100, y))
            
            center_points.append((int(x), int(y)))
        
        self.center_points_by_face[face_id] = center_points
    
    # 移除不再需要的方法，因為邏輯已經整合到 update_faces 中
    
    def set_flicker_state_for_face(self, face_id, should_flicker):
        """設置特定人臉的窗口閃爍狀態"""
        if face_id in self.windows_by_face:
            for window in self.windows_by_face[face_id]:
                window.set_force_flicker(should_flicker)
    
    def draw_windows_for_face(self, frame, face_id, color_bgr=(255, 255, 255)):
        """繪製特定人臉的所有窗口"""
        if face_id in self.windows_by_face:
            for window in self.windows_by_face[face_id]:
                window.draw_on_cv_frame(frame, color_bgr)
    
    def draw_all_windows(self, frame, color_bgr=(255, 255, 255)):
        """繪製所有窗口（包括人臉檢測和獨立模式）"""
        # 繪製人臉檢測相關的窗口
        for face_id in self.windows_by_face:
            self.draw_windows_for_face(frame, face_id, color_bgr)
        
        # 繪製獨立模式的窗口
        self.draw_standalone_windows(frame, color_bgr)
    
    def clear_all_windows(self):
        """清除所有窗口（包括獨立模式）"""
        self.windows_by_face.clear()
        self.center_points_by_face.clear()
        self.standalone_windows.clear()
        self.standalone_center_points.clear()
    
    def get_window_count_for_face(self, face_id):
        """獲取特定人臉的窗口數量"""
        return len(self.windows_by_face.get(face_id, []))
    
    def get_total_window_count(self):
        """獲取總窗口數量"""
        face_windows = sum(len(windows) for windows in self.windows_by_face.values())
        standalone_windows = len(self.standalone_windows) if self.standalone_mode else 0
        return face_windows + standalone_windows
    
    def enable_standalone_mode(self, enable=True):
        """啟用/禁用獨立模式"""
        self.standalone_mode = enable
        if enable:
            self.generate_standalone_center_points()
            print(f"獨立模式已啟用，生成 {len(self.standalone_center_points)} 個中心點")
        else:
            self.standalone_windows.clear()
            self.standalone_center_points.clear()
            print("獨立模式已禁用")
    
    def generate_standalone_center_points(self):
        """為獨立模式生成中心點"""
        self.standalone_center_points.clear()
        
        # 在屏幕中心區域生成中心點
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        for i in range(STANDALONE_CENTER_COUNT):
            if i == 0:
                # 第一個點在屏幕中心附近
                px = center_x + random.randint(-50, 50)
                py = center_y + random.randint(-50, 50)
            else:
                # 其他點圍繞中心分布
                angle = (i * 360 / STANDALONE_CENTER_COUNT) + random.randint(-45, 45)
                distance = STANDALONE_CENTER_SPREAD * random.uniform(0.8, 1.2)
                rad = math.radians(angle)
                px = center_x + distance * math.cos(rad)
                py = center_y + distance * math.sin(rad)
                
                # 確保點在屏幕範圍內
                px = max(100, min(self.screen_width - 100, px))
                py = max(100, min(self.screen_height - 100, py))
            
            self.standalone_center_points.append((int(px), int(py)))
    
    def update_standalone_mode(self):
        """更新獨立模式的窗口 - 限制數量為4個"""
        if not self.standalone_mode:
            return
            
        global frame_count
        frame_count += 1
        
        # 限制獨立模式窗口數量為4個
        MAX_STANDALONE_WINDOWS = 4
        if len(self.standalone_windows) < MAX_STANDALONE_WINDOWS:
            # 隨機生成新窗口
            if random.random() < STANDALONE_SPAWN_RATE and self.standalone_center_points:
                new_position = self.find_valid_standalone_position()
                if new_position:
                    # 使用平均窗口大小
                    average_face_size = 200
                    new_window = CalWindowForDetection(new_position[0], new_position[1], average_face_size)
                    self.standalone_windows.append(new_window)
        
        # 更新現有窗口並移除已死亡的
        self.standalone_windows = [w for w in self.standalone_windows if w.update()]
    
    def find_valid_standalone_position(self):
        """為獨立模式找到合適的窗口位置"""
        MIN_DISTANCE_BETWEEN_WINDOWS = 200  # 獨立模式窗口間距稍大
        
        # 嘗試多次找到合適的位置
        for attempt in range(15):
            if self.standalone_center_points:
                candidate = random.choice(self.standalone_center_points)
                
                # 檢查與其他窗口的距離
                too_close = False
                for window in self.standalone_windows:
                    dist_to_window = ((candidate[0] - window.center_x)**2 + (candidate[1] - window.center_y)**2)**0.5
                    if dist_to_window < MIN_DISTANCE_BETWEEN_WINDOWS:
                        too_close = True
                        break
                
                if not too_close:
                    return candidate
        
        return None  # 找不到合適位置
    
    def draw_standalone_windows(self, frame, color_bgr=(255, 255, 255)):
        """繪製獨立模式的窗口"""
        if not self.standalone_mode:
            return
            
        for window in self.standalone_windows:
            window.draw_on_cv_frame(frame, color_bgr)
    
    def set_standalone_flicker_state(self, should_flicker):
        """設置獨立模式窗口的閃爍狀態"""
        if self.standalone_mode:
            for window in self.standalone_windows:
                window.set_force_flicker(should_flicker) 