import sys
import random
import math
import time
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPolygon, QFont
from PyQt6.QtCore import QTimer, Qt, QPoint, QPointF, QRectF



# ===== 配置參數 =====
# 視窗生成
SPAWN_RATE = 0.1 # 每幀生成視窗的機率 (0.01-0.1)
MIN_LIFE = 200     # 視窗最小生命值
MAX_LIFE = 400     # 視窗最大生命值
LIFE_DECAY = 1     # 每幀生命值衰減

# 視窗大小 (16:9 比例，對應PDE的160:100)
WINDOW_WIDTH_DEFAULT = 160    # 預設寬度
WINDOW_HEIGHT_DEFAULT = 100   # (16:9比例)

# 視窗位置
MIN_RADIUS = 200   # 最小距離中心點距離
MAX_RADIUS = 350   # 最大距離中心點距離
MAX_PHI = 25       # 最大垂直角度

# 中心點配置
CENTER_POINTS_COUNT = 4    # 中心點數量
CENTER_SPREAD = 120        # 中心點擴散範圍

# 視窗類型
WINDOW_TYPES = 16   # 視窗內容類型數量

# 顯示配置
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# ===== 動畫速度配置 =====
# 使用與Processing相同的時間係數
ANIMATION_SPEED_MULTIPLIER = 1.0   # 全域動畫速度倍數
CONTENT_ANIMATION_SPEED = 0.1      # 內容動畫基礎速度 (對應Processing的frameCount*0.1)
TIME_SCALE = 0.1                   # 時間縮放係數 (對應Processing的frameCount*0.1)

# 全域frame_count變數
frame_count = 0

# 更接近 Processing 的 noise 實現 - 更跳動、更隨機
class ProcessingStyleNoise:
    def __init__(self):
        # 建立查找表
        self.noise_table = {}
        self.random_seed = random.randint(0, 10000)
        
    def noise(self, x, y=0, z=0):
        # 使用離散化的座標來產生更跳動的效果
        # Processing 的 noise 在小範圍內變化很大
        
        # 將座標離散化
        grid_size = 0.5  # 更大的網格產生更跳動的效果
        x_grid = int(x / grid_size)
        y_grid = int(y / grid_size) 
        z_grid = int(z / grid_size)
        
        # 計算網格內的插值位置
        x_fract = (x / grid_size) - x_grid
        y_fract = (y / grid_size) - y_grid
        z_fract = (z / grid_size) - z_grid
        
        # 為每個網格點生成隨機值
        def grid_random(gx, gy, gz):
            # 使用座標作為種子產生偽隨機數
            seed = (gx * 73856093) ^ (gy * 19349663) ^ (gz * 83492791) ^ self.random_seed
            random.seed(seed)
            return random.random()
        
        # 獲取8個角點的值
        v000 = grid_random(x_grid, y_grid, z_grid)
        v001 = grid_random(x_grid, y_grid, z_grid + 1)
        v010 = grid_random(x_grid, y_grid + 1, z_grid)
        v011 = grid_random(x_grid, y_grid + 1, z_grid + 1)
        v100 = grid_random(x_grid + 1, y_grid, z_grid)
        v101 = grid_random(x_grid + 1, y_grid, z_grid + 1)
        v110 = grid_random(x_grid + 1, y_grid + 1, z_grid)
        v111 = grid_random(x_grid + 1, y_grid + 1, z_grid + 1)
        
        # 使用更陡峭的插值函數，產生更跳動的效果
        def sharp_interp(t):
            # 使用更陡峭的曲線
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
        
        # 增加對比度，讓變化更明顯
        result = (result - 0.5) * 1 + 0.3
        
        return max(0, min(1, result))

# 建立全域 noise 物件
perlin = ProcessingStyleNoise()

def pde_noise(x, y=0, z=0):
    """模擬Processing的noise函數 - 更跳動的版本"""
    return perlin.noise(x, y, z)


class CalWindow:
    def __init__(self, center_x, center_y):
        self.center_x = center_x
        self.center_y = center_y
        
        # 視窗屬性 - 使用Processing的預設大小
        self.width = WINDOW_WIDTH_DEFAULT
        self.height = WINDOW_HEIGHT_DEFAULT
        self.window_kind = random.randint(1, WINDOW_TYPES)
        self.life = random.randint(MIN_LIFE, MAX_LIFE)
        self.max_life = self.life
        self.display = True
        
        # 極座標位置
        self.r = random.uniform(MIN_RADIUS, MAX_RADIUS)
        self.theta = random.uniform(0, 360)
        self.phi = random.uniform(-MAX_PHI, MAX_PHI)
        
        # 計算笛卡爾座標位置
        self.update_position()
        
        # 動畫屬性 - 這個很重要！每個視窗有自己的i值
        self.i = random.randint(0, 1000)  # 對應PDE中的i變數
        self.alpha = 1.0
        self.mode = 3  # 對應PDE的Mode系統
        
        # 連接線偏移 - 使用與Processing相同的計算方式
        # Processing: Temp_Shift_X = (Px-Bx)*random(0.2, 0.5)
        # 這裡簡化為基於視窗位置的隨機偏移
        self.connection_offset_x = random.uniform(-40, 40)
        self.connection_offset_y = random.uniform(-25, 25)
        
        # Quadrant for connection lines (對應Processing的Quadrant)
        self.quadrant = random.randint(0, 3)
        
    def update_position(self):
        rad_theta = math.radians(self.theta)
        rad_phi = math.radians(self.phi)
        
        self.x = self.center_x + self.r * math.cos(rad_theta) * math.cos(rad_phi)
        self.y = self.center_y + self.r * math.sin(rad_theta) * math.cos(rad_phi)
        
    def update(self):
        self.life -= LIFE_DECAY
        
        # 更新模式 (對應Processing的Mode系統)
        if self.life >= self.max_life * 0.8:
            self.mode = 3
        elif self.life >= self.max_life * 0.2:
            self.mode = 2
        elif self.life > 0:
            self.mode = 1
        else:
            self.mode = 0
            
        # 根據模式更新顯示狀態 (對應Processing的邏輯)
        if self.mode == 3:  # 初始閃爍
            self.display = (self.life % 2 == 0)
            self.alpha = 1.0  # Processing使用Enter_Light，這裡簡化為1.0
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
    
    def draw(self, painter):
        if not self.display:
            return
            
        painter.setOpacity(self.alpha)
        
        # 繪製連接線 - 使用與Processing相同的透明度邏輯
        connection_alpha = int(50 * self.alpha)  # 對應Processing的50*Enter_Light
        pen = QPen(QColor(255, 255, 255, connection_alpha), 1)
        painter.setPen(pen)
        
        # 使用與PDE相同的連接線邏輯
        painter.drawLine(int(self.x), int(self.y), 
                        int(self.x - self.connection_offset_x), 
                        int(self.y - self.connection_offset_y))
        painter.drawLine(int(self.x - self.connection_offset_x), 
                        int(self.y - self.connection_offset_y), 
                        int(self.center_x), int(self.center_y))
        
        # 繪製視窗框架 - 使用與Processing相同的透明度邏輯
        frame_alpha = int(100 * self.alpha)  # 對應Processing的100*Enter_Light
        pen = QPen(QColor(255, 255, 255, frame_alpha), 1)
        painter.setPen(pen)
        painter.setBrush(QBrush())
        
        # 主視窗框架
        wx = int(self.x - self.width/2)
        wy = int(self.y - self.height/2)
        painter.drawRect(wx, wy, self.width, self.height)
        
        # 內框 (0.92倍寬度，從頂部3像素開始)
        inner_x = int(self.x - self.width * 0.46)
        inner_y = int(self.y - self.height * 0.4)
        inner_w = int(self.width * 0.92)
        inner_h = int(self.height * 0.8)
        painter.drawRect(inner_x, inner_y, inner_w, inner_h)
        
        # 標題欄按鈕
        painter.drawRect(wx + 6, wy + 3, 6, 6)
        painter.drawRect(wx + 20, wy + 3, 6, 6)
        
        # 繪製內容
        self.draw_content(painter, self.x, self.y)
        painter.setOpacity(1.0)
    
    def draw_content(self, painter, cx, cy):
        """繪製視窗內容，cx和cy是視窗中心座標"""
        # 使用與Processing相同的透明度邏輯
        content_alpha = int(100 * self.alpha)  # 對應Processing的100*Enter_Light
        pen = QPen(QColor(255, 255, 255, content_alpha), 1)
        painter.setPen(pen)
        
        # 保存原始變換狀態
        painter.save()
        painter.translate(cx, cy)
        
        if self.window_kind == 1:      # Bar chart
            self.draw_bar_chart(painter)
        elif self.window_kind == 2:    # Line chart with points
            self.draw_line_chart(painter)
        elif self.window_kind == 3:    # Curve chart with vertical lines
            self.draw_curve_chart(painter)
        elif self.window_kind == 4:    # Matrix display
            self.draw_matrix_display(painter)
        elif self.window_kind == 5:    # Geometric pattern (8 triangles)
            self.draw_geometric_pattern(painter)
        elif self.window_kind == 6:    # Grid pattern
            self.draw_grid_pattern(painter)
        elif self.window_kind == 7:    # Oscilloscope
            self.draw_oscilloscope(painter)
        elif self.window_kind == 8:    # Radar pattern
            self.draw_radar_pattern(painter)
        elif self.window_kind == 9:    # Complex rotating shapes
            self.draw_complex_shapes(painter)
        elif self.window_kind == 10:   # Crosshair pattern
            self.draw_crosshair_pattern(painter)
        elif self.window_kind == 11:   # Diamond and trapezoid shapes
            self.draw_diamond_shapes(painter)
        elif self.window_kind == 12:   # Level indicators with circles
            self.draw_level_indicators(painter)
        elif self.window_kind == 13:   # Progress bars
            self.draw_progress_bars(painter)
        elif self.window_kind == 14:   # Vertical oscilloscope
            self.draw_vertical_oscilloscope(painter)
        elif self.window_kind == 15:   # Orbital pattern
            self.draw_orbital_pattern(painter)
        elif self.window_kind == 16:   # Stacked bars with grid
            self.draw_stacked_bars(painter)
        
        painter.restore()
    
    def draw_bar_chart(self, painter):
        # 16個bar，使用與Processing相同的時間係數
        for i in range(16):
            # 使用與Processing相同的時間係數 frameCount*0.1
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            bar_height = int(70 * noise_val)
            bar_x = -70 + i * 9
            bar_y = 40
            painter.drawRect(bar_x, bar_y, 6, -bar_height)
    
    def draw_line_chart(self, painter):
        # 繪製折線圖，使用與Processing相同的時間係數
        points = []
        for i in range(16):
            px = -67.5 + i * 9
            # 使用與Processing相同的時間係數 frameCount*0.1
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = 40 - 70 * noise_val
            points.append((px, py))
        
        # 畫15條連接線
        for i in range(15):
            painter.drawLine(int(points[i][0]), int(points[i][1]), 
                           int(points[i+1][0]), int(points[i+1][1]))
        
        # 畫16個點
        for px, py in points:
            painter.drawEllipse(int(px-2), int(py-2), 4, 4)
    
    def draw_curve_chart(self, painter):
        # 曲線圖加基準線和垂直線，使用與Processing相同的時間係數
        points = []
        for i in range(16):
            px = -67.5 + i * 9
            noise_val = pde_noise(i, frame_count * CONTENT_ANIMATION_SPEED)
            py = 40 - 70 * noise_val
            points.append((px, py))
        
        # 畫曲線
        for i in range(len(points) - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]), 
                           int(points[i+1][0]), int(points[i+1][1]))
        
        # 基準線
        painter.drawLine(-67, 8, 77, 8)
        
        # 垂直線
        for i in range(16):
            px = points[i][0]
            py = points[i][1]
            painter.drawLine(int(px), 8, int(px), int(py))
    
    def draw_matrix_display(self, painter):
        # 9x3 矩陣顯示，使用與Processing相同的時間係數
        painter.setBrush(QBrush())
        for i in range(9):
            for j in range(3):
                # 使用與Processing相同的時間係數 frameCount*0.1
                noise_val = pde_noise(i, j, frame_count * CONTENT_ANIMATION_SPEED)
                text_val = int(noise_val * 10)
                body_val = int(noise_val * 20)
                px = -62.5 + i * 15
                py = -25 + j * 20
                self.draw_shaba_text(painter, text_val, body_val, px, py)
    
    def draw_shaba_text(self, painter, tag_point, tag_body, px, py):
        # 模擬PDE的Shaba_Text函數
        painter.save()
        painter.translate(px, py)
        
        # 畫點
        if tag_point == 1:
            painter.drawRect(0, 0, 2, 2)
        elif tag_point == 2:
            painter.drawRect(6, 0, 2, 2)
        elif tag_point == 3:
            painter.drawRect(0, 0, 2, 2)
            painter.drawRect(6, 0, 2, 2)
        
        # 畫主體 - 限制body值範圍
        tag_body = tag_body % 8
        if tag_body == 0:
            painter.drawLine(1, 5, 1, 11)
            painter.drawLine(1, 11, 7, 11)
            painter.drawLine(7, 11, 7, 5)
        elif tag_body == 1:
            painter.drawLine(1, 5, 7, 5)
            painter.drawLine(1, 5, 1, 11)
            painter.drawLine(1, 11, 7, 11)
        elif tag_body == 2:
            painter.drawLine(1, 5, 7, 5)
            painter.drawLine(1, 5, 1, 11)
            painter.drawLine(7, 11, 7, 5)
        elif tag_body == 3:
            painter.drawLine(1, 5, 7, 5)
            painter.drawLine(1, 11, 7, 11)
            painter.drawLine(7, 11, 7, 5)
        elif tag_body == 4:
            painter.drawLine(1, 5, 7, 5)
            painter.drawLine(1, 5, 1, 11)
        elif tag_body == 5:
            painter.drawLine(1, 5, 1, 11)
            painter.drawLine(1, 11, 7, 11)
        elif tag_body == 6:
            painter.drawLine(1, 11, 7, 11)
            painter.drawLine(7, 11, 7, 5)
        elif tag_body == 7:
            painter.drawLine(1, 5, 7, 5)
            painter.drawLine(7, 11, 7, 5)
        
        painter.restore()
    
    def draw_geometric_pattern(self, painter):
        # 8個三角形圖案，使用與Processing相同的時間係數
        for j in range(8):
            fill_noise = pde_noise(self.i + j, frame_count * CONTENT_ANIMATION_SPEED)
            if fill_noise > 0.5:
                # 使用與Processing相同的透明度邏輯
                fill_alpha = int(100 * self.alpha)
                painter.setBrush(QBrush(QColor(255, 255, 255, fill_alpha)))
            else:
                painter.setBrush(QBrush())
            
            # 根據PDE代碼繪製不同的三角形
            if j == 0:  # 中心三角形
                points = [QPoint(0, 0), QPoint(-20, -30), QPoint(20, -30)]
            elif j == 1:  # 右上
                points = [QPoint(10, -3), QPoint(30, -30), QPoint(65, -30), QPoint(65, -20)]
            elif j == 2:  # 右中
                points = [QPoint(10, 5), QPoint(65, -10), QPoint(65, 10)]
            elif j == 3:  # 右下
                points = [QPoint(10, 13), QPoint(65, 20), QPoint(65, 35), QPoint(30, 35)]
            elif j == 4:  # 下
                points = [QPoint(0, 10), QPoint(20, 35), QPoint(-20, 35)]
            elif j == 5:  # 左下
                points = [QPoint(-10, 13), QPoint(-30, 35), QPoint(-65, 35), QPoint(-65, 20)]
            elif j == 6:  # 左中
                points = [QPoint(-10, 5), QPoint(-65, 10), QPoint(-65, -10)]
            else:  # 左上
                points = [QPoint(-10, -3), QPoint(-65, -20), QPoint(-65, -30), QPoint(-30, -30)]
            
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
    
    def draw_grid_pattern(self, painter):
        # 16x3 網格，使用與Processing相同的時間係數
        for i in range(16):
            for j in range(3):
                temp_value = pde_noise((j * 16 + i), frame_count * 0.01)  # 對應Processing的frameCount*0.01
                px = int(-self.width * 0.4 + self.width * 0.05 * i)
                py = int(-self.height * 0.3 + self.height * 0.23 * j)
                cell_w = int(self.width * 0.05)
                cell_h = int(self.height * 0.2)
                
                if temp_value > 0.7:
                    # 使用與Processing相同的透明度邏輯
                    fill_alpha = int(100 * self.alpha)
                    painter.setBrush(QBrush(QColor(255, 255, 255, fill_alpha)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(px, py, cell_w, cell_h)
                    # 恢復畫筆設置，確保寬度為1
                    painter.setPen(QPen(QColor(255, 255, 255, fill_alpha), 1))
                elif temp_value > 0.6:
                    painter.setBrush(QBrush())
                    painter.drawRect(px, py, cell_w, cell_h)
    
    def draw_oscilloscope(self, painter):
        # 4條水平線加移動點，使用與Processing相同的時間係數
        painter.setBrush(QBrush())
        for i in range(4):
            temp_value = pde_noise(i + 2, frame_count * 0.01)  # 對應Processing的frameCount*0.01
            line_y = int(-self.height * 0.15 + i * 0.15 * self.height)
            painter.drawLine(int(-self.width * 0.4), line_y, int(self.width * 0.4), line_y)
            
            # 動態點
            dot_x = int(-self.width * 0.4 + temp_value * self.width * 0.8)
            painter.drawEllipse(dot_x - 2, line_y - 2, 5, 5)
    
    def draw_radar_pattern(self, painter):
        # 雷達圖案，使用與Processing相同的時間係數
        painter.setBrush(QBrush())
        painter.drawEllipse(-5, -5, 10, 10)
        painter.drawLine(int(-self.width * 0.4), 0, int(self.width * 0.4), 0)
        
        for i in range(6):
            temp_value = pde_noise(i + 8, frame_count * 0.02)  # 對應Processing的frameCount*0.02
            radius = 10 + i * 5
            start_angle = int(360 * temp_value * 16)  # Qt uses 1/16 degree units
            span_angle = (30 + i * 8) * 16
            
            painter.drawArc(-radius, -radius, radius * 2, radius * 2, start_angle, span_angle)
    
    def draw_complex_shapes(self, painter):
        # 複雜旋轉形狀，使用與Processing相同的時間係數
        painter.drawEllipse(-5, -5, 10, 10)
        
        for i in range(6):
            temp_value = pde_noise(i * 1.5 + 9, frame_count * 0.03)  # 對應Processing的frameCount*0.03
            painter.save()
            painter.rotate(360 * temp_value)
            
            fill_noise = pde_noise(i + 108, frame_count * 0.07)  # 對應Processing的frameCount*0.07
            if fill_noise > 0.5:
                # 使用與Processing相同的透明度邏輯
                fill_alpha = int(100 * self.alpha)
                painter.setBrush(QBrush(QColor(50, 50, 50, fill_alpha)))
            else:
                painter.setBrush(QBrush())
            
            # 繪製多邊形
            points = []
            for j in range(i*2+8):
                angle_rad = math.radians(j * 7)
                x1 = i*2*3 * math.cos(angle_rad)
                y1 = i*2*3 * math.sin(angle_rad)
                points.append(QPoint(int(x1), int(y1)))
            
            for j in range(i*2+7, -1, -1):
                angle_rad = math.radians(j * 7)
                x2 = (i*2+1)*3 * math.cos(angle_rad)
                y2 = (i*2+1)*3 * math.sin(angle_rad)
                points.append(QPoint(int(x2), int(y2)))
            
            if points:
                polygon = QPolygon(points)
                painter.drawPolygon(polygon)
            
            painter.restore()
    
    def draw_crosshair_pattern(self, painter):
        # 十字準星圖案，使用與Processing相同的時間係數
        temp_x1 = pde_noise(self.i + 110, frame_count * 0.013)  # 對應Processing的frameCount*0.013
        temp_y1 = pde_noise(self.i + 111, frame_count * 0.012)  # 對應Processing的frameCount*0.012
        temp_x2 = pde_noise(self.i + 112, frame_count * 0.014)  # 對應Processing的frameCount*0.014
        temp_y2 = pde_noise(self.i + 113, frame_count * 0.015)  # 對應Processing的frameCount*0.015
        
        # 第一組十字線
        line_y1 = temp_y1 * self.height * 0.9 - self.height * 0.45
        line_x1 = temp_x1 * self.width - self.width * 0.5
        painter.drawLine(int(-self.width * 0.45), int(line_y1), int(self.width * 0.45), int(line_y1))
        painter.drawLine(int(line_x1), int(-self.height * 0.35), int(line_x1), int(self.height * 0.4))
        
        # 第一組標記
        pen = painter.pen()
        mark_alpha = int(100 * self.alpha)  # 使用與Processing相同的透明度邏輯
        pen.setColor(QColor(100, 100, 100, mark_alpha))
        pen.setWidth(1)  # 確保寬度為1
        painter.setPen(pen)
        
        # 繪製十字準星的小標記
        offsets = [
            (0.02, -0.03), (0.05, -0.03), (-0.02, -0.03), (-0.05, -0.03),
            (0.02, 0.03), (0.05, 0.03), (-0.02, 0.03), (-0.05, 0.03)
        ]
        
        for dx, dy in offsets:
            mark_x = int(-self.width * 0.5 + (temp_x1 + dx) * self.width)
            mark_y = int((temp_y1 + dy) * self.height * 0.9 - self.height * 0.45)
            if abs(dx) > abs(dy):  # 水平線
                painter.drawLine(mark_x - 3, mark_y, mark_x + 3, mark_y)
            else:  # 垂直線
                painter.drawLine(mark_x, mark_y - 4, mark_x, mark_y + 4)
        
        # 恢復原色
        content_alpha = int(100 * self.alpha)  # 使用與Processing相同的透明度邏輯
        pen.setColor(QColor(255, 255, 255, content_alpha))
        pen.setWidth(1)  # 確保寬度為1
        painter.setPen(pen)
        
        # 第二組十字線
        line_y2 = temp_y2 * self.height * 0.9 - self.height * 0.45
        line_x2 = temp_x2 * self.width - self.width * 0.5
        painter.drawLine(int(-self.width * 0.45), int(line_y2), int(self.width * 0.45), int(line_y2))
        painter.drawLine(int(line_x2), int(-self.height * 0.35), int(line_x2), int(self.height * 0.4))
    
    def draw_diamond_shapes(self, painter):
        # 鑽石和梯形形狀，使用與Processing相同的時間係數
        shapes = [
            # 中心鑽石
            [(0, int(-self.height * 0.3)), 
             (int(self.width * 0.1), int(self.height * 0.025)), 
             (0, int(self.height * 0.35)), 
             (int(-self.width * 0.1), int(self.height * 0.025))],
            # 其他8個形狀
            [(int(self.width * 0.1), int(-self.height * 0.3)), 
             (int(self.width * 0.2), int(-self.height * 0.3)), 
             (int(self.width * 0.3), int(-self.height * 0.05)), 
             (int(self.width * 0.2), int(-self.height * 0.05))],
            [(int(self.width * 0.1), int(self.height * 0.35)), 
             (int(self.width * 0.2), int(self.height * 0.35)), 
             (int(self.width * 0.3), int(self.height * 0.1)), 
             (int(self.width * 0.2), int(self.height * 0.1))],
            [(int(-self.width * 0.1), int(-self.height * 0.3)), 
             (int(-self.width * 0.2), int(-self.height * 0.3)), 
             (int(-self.width * 0.3), int(-self.height * 0.05)), 
             (int(-self.width * 0.2), int(-self.height * 0.05))],
            [(int(-self.width * 0.1), int(self.height * 0.35)), 
             (int(-self.width * 0.2), int(self.height * 0.35)), 
             (int(-self.width * 0.3), int(self.height * 0.1)), 
             (int(-self.width * 0.2), int(self.height * 0.1))],
            [(int(self.width * 0.3), int(-self.height * 0.3)), 
             (int(self.width * 0.4), int(-self.height * 0.3)), 
             (int(self.width * 0.4), int(-self.height * 0.05))],
            [(int(self.width * 0.3), int(self.height * 0.35)), 
             (int(self.width * 0.4), int(self.height * 0.35)), 
             (int(self.width * 0.4), int(self.height * 0.1))],
            [(int(-self.width * 0.3), int(-self.height * 0.3)), 
             (int(-self.width * 0.4), int(-self.height * 0.3)), 
             (int(-self.width * 0.4), int(-self.height * 0.05))],
            [(int(-self.width * 0.3), int(self.height * 0.35)), 
             (int(-self.width * 0.4), int(self.height * 0.35)), 
             (int(-self.width * 0.4), int(self.height * 0.1))]
        ]
        
        for i, shape_points in enumerate(shapes):
            fill_noise = pde_noise(self.i + 111 + i, frame_count * 0.021)  # 對應Processing的frameCount*0.021
            if fill_noise > 0.5:
                # 使用與Processing相同的透明度邏輯
                fill_alpha = int(100 * self.alpha)
                painter.setBrush(QBrush(QColor(150, 150, 150, fill_alpha)))
            else:
                painter.setBrush(QBrush())
            
            points = [QPoint(x, y) for x, y in shape_points]
            if len(points) >= 3:
                polygon = QPolygon(points)
                painter.drawPolygon(polygon)
    
    def draw_level_indicators(self, painter):
        # 等級指示器，使用與Processing相同的時間係數
        temp_value = pde_noise(self.i + 13, frame_count * 0.1)  # 對應Processing的frameCount*0.1
        temp_value = temp_value * 15 - 1
        
        # 垂直等級條
        for i in range(13):
            if i <= temp_value:
                # 使用與Processing相同的透明度邏輯
                fill_alpha = int(100 * self.alpha)
                painter.setBrush(QBrush(QColor(50, 50, 50, fill_alpha)))
            else:
                painter.setBrush(QBrush())
            
            bar_y = int(self.height * 0.35 - self.height * 0.05 * i)
            bar_h = int(self.height * 0.05)
            painter.drawRect(int(-self.width * 0.05), bar_y - bar_h, 
                           int(self.width * 0.1), bar_h)
        
        # 側邊標記點
        painter.setBrush(QBrush())
        for i in range(0, 13, 2):
            mark_y = int(self.height * 0.35 - self.height * 0.05 * i)
            painter.drawEllipse(int(-self.width * 0.1) - 2, mark_y - 2, 4, 4)
            painter.drawEllipse(int(self.width * 0.1) - 2, mark_y - 2, 4, 4)
        
        # 圓形圖案，使用與Processing相同的時間係數
        temp_values = [
            pde_noise(self.i + 113, frame_count * 0.1),  # 對應Processing的frameCount*0.1
            pde_noise(self.i + 114, frame_count * 0.1),
            pde_noise(self.i + 115, frame_count * 0.1),
            pde_noise(self.i + 116, frame_count * 0.1)
        ]
        
        # 左側圓形
        center_x = int(-self.width * 0.3)
        center_y = int(-self.height * 0.15)
        painter.drawEllipse(center_x - 5, center_y - 5, 10, 10)
        painter.drawArc(center_x - 10, center_y - 10, 20, 20, 
                       int(360 * temp_values[0] * 16), int(170 * 16))
        painter.drawArc(center_x - 15, center_y - 15, 30, 30, 
                       int(360 * temp_values[2] * 16), int(90 * 16))
        
        # 右側圓形
        center_x = int(self.width * 0.3)
        painter.drawEllipse(center_x - 5, center_y - 5, 10, 10)
        painter.drawArc(center_x - 10, center_y - 10, 20, 20, 
                       int(360 * temp_values[1] * 16), int(170 * 16))
        painter.drawArc(center_x - 15, center_y - 15, 30, 30, 
                       int(360 * temp_values[3] * 16), int(90 * 16))
    
    def draw_progress_bars(self, painter):
        # 進度條，使用與Processing相同的時間係數
        painter.setBrush(QBrush())
        for i in range(4):
            temp_value = pde_noise(i + 1, frame_count * 0.1)  # 對應Processing的frameCount*0.1
            bar_y = int(-self.height * (0.25 - 0.15 * i))
            bar_h = int(self.height * 0.1)
            
            # 填充部分
            filled_width = int(temp_value * self.width * 0.8) - 2
            painter.drawRect(int(-self.width * 0.4), bar_y, filled_width, bar_h)
            
            # 空白部分
            empty_start = int(-self.width * 0.4) + filled_width + 3
            empty_width = int(self.width * 0.8) - filled_width - 3
            painter.drawRect(empty_start, bar_y, empty_width, bar_h)
    
    def draw_vertical_oscilloscope(self, painter):
        # 垂直示波器，使用與Processing相同的時間係數
        painter.setBrush(QBrush())
        for i in range(16):
            bar_x = -70 + i * 9
            noise_val = pde_noise(i, frame_count * 0.1)  # 對應Processing的frameCount*0.1
            
            # 向上的線
            painter.drawLine(bar_x, 5, bar_x, int(5 - 35 * noise_val))
            # 向下的線
            painter.drawLine(bar_x, 5, bar_x, int(5 + 35 * noise_val))
    
    def draw_orbital_pattern(self, painter):
        # 軌道圖案，使用與Processing相同的時間係數
        temp_values = [
            pde_noise(self.i + 215, frame_count * 0.1),  # 對應Processing的frameCount*0.1
            pde_noise(self.i + 216, frame_count * 0.1),
            pde_noise(self.i + 217, frame_count * 0.1)
        ]
        
        center_x = int(-self.width * 0.15)
        center_y = int(self.height * 0.05)
        
        # 三個同心圓
        painter.setBrush(QBrush())
        r1 = int(self.width * 0.05)
        painter.drawEllipse(center_x - r1, center_y - r1, r1 * 2, r1 * 2)
        r2 = int(self.width * 0.125)
        painter.drawEllipse(center_x - r2, center_y - r2, r2 * 2, r2 * 2)
        r3 = int(self.width * 0.2)
        painter.drawEllipse(center_x - r3, center_y - r3, r3 * 2, r3 * 2)
        
        # 基準點
        base_x = int(-self.width * 0.05)
        base_y = int(self.height * 0.05)
        
        # 軌道線和軌道點
        radii = [self.width * 0.05, self.width * 0.125, self.width * 0.2]
        for i, (radius, temp_val) in enumerate(zip(radii, temp_values)):
            angle_rad = math.radians(temp_val * 360)
            orbit_x = int(radius * math.cos(angle_rad)) + center_x
            orbit_y = int(radius * math.sin(angle_rad)) + center_y
            
            # 連接線
            painter.drawLine(base_x, base_y, orbit_x, orbit_y)
            
            # 軌道點
            point_r = int(self.width * 0.025)
            painter.drawEllipse(orbit_x - point_r, orbit_y - point_r, 
                               point_r * 2, point_r * 2)
    
    def draw_stacked_bars(self, painter):
        # 堆疊條形圖，使用與Processing相同的時間係數
        temp_values = [
            pde_noise(self.i + 215, frame_count * 0.1),  # 對應Processing的frameCount*0.1
            pde_noise(self.i + 216, frame_count * 0.1),
            pde_noise(self.i + 217, frame_count * 0.1)
        ]
        
        # 水平網格線
        painter.setBrush(QBrush())
        for i in range(14):
            line_y = int(-self.height * (0.3 - i * 0.05))
            painter.drawLine(int(-self.width * 0.4), line_y, 
                           int(self.width * 0.4), line_y)
        
        # 三個堆疊條
        fill_alpha = int(100 * self.alpha)  # 使用與Processing相同的透明度邏輯
        painter.setBrush(QBrush(QColor(50, 50, 50, fill_alpha)))
        
        # 左條
        bar_height = int(temp_values[0] * self.height * 0.9)
        painter.drawRect(int(-self.width * 0.25), int(self.height * 0.4), 
                        int(self.width * 0.1), -bar_height)
        
        # 中條
        bar_height = int(temp_values[1] * self.height * 0.9)
        painter.drawRect(int(-self.width * 0.05), int(self.height * 0.4), 
                        int(self.width * 0.1), -bar_height)
        
        # 右條
        bar_height = int(temp_values[2] * self.height * 0.9)
        painter.drawRect(int(self.width * 0.15), int(self.height * 0.4), 
                        int(self.width * 0.1), -bar_height)


class WindowEffect(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setWindowTitle("Window Effect - Processing Style")
        self.setStyleSheet("background-color: black;")
        
        # 效果屬性
        self.windows = []
        self.effect_active = True
        self.center_points = []
        
        # 動畫計時器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(1000 // FPS)
        
        # 生成中心點
        self.generate_center_points()
        
    def generate_center_points(self):
        """生成隨機中心點"""
        self.center_points.clear()
        base_x, base_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        for i in range(CENTER_POINTS_COUNT):
            if i == 0:
                x = base_x + random.randint(-30, 30)
                y = base_y + random.randint(-30, 30)
            else:
                angle = (i * 360 / CENTER_POINTS_COUNT) + random.randint(-20, 20)
                distance = CENTER_SPREAD + random.randint(-30, 30)
                rad = math.radians(angle)
                x = base_x + distance * math.cos(rad)
                y = base_y + distance * math.sin(rad)
            
            self.center_points.append((int(x), int(y)))
    
    def spawn_window(self, center_x, center_y, window_kind=None):
        """生成新視窗的公開方法"""
        new_window = CalWindow(center_x, center_y)
        if window_kind is not None:
            new_window.window_kind = window_kind
        self.windows.append(new_window)
        return new_window
    
    def update_animation(self):
        global frame_count
        frame_count += 1
        
        if self.effect_active and self.center_points:
            # 隨機生成新視窗
            if random.random() < SPAWN_RATE:
                center_x, center_y = random.choice(self.center_points)
                self.spawn_window(center_x, center_y)
            
            # 更新現有視窗並移除已死亡的
            self.windows = [w for w in self.windows if w.update()]
        
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        if self.effect_active:
            # 繪製中心點
            colors = [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), 
                     QColor(255, 255, 0), QColor(255, 0, 255), QColor(0, 255, 255)]
            
            for i, (cx, cy) in enumerate(self.center_points):
                color = colors[i % len(colors)]
                painter.setPen(QPen(color, 1))  # 改為1像素寬度，與視窗線條一致
                painter.setBrush(QBrush(color))
                painter.drawEllipse(cx - 3, cy - 3, 6, 6)
            
            # 繪製所有視窗
            for window in self.windows:
                window.draw(painter)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.effect_active = not self.effect_active
        elif event.key() == Qt.Key.Key_C:
            self.windows.clear()
        elif event.key() == Qt.Key.Key_R:
            self.generate_center_points()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_9:
            # 按數字鍵生成特定類型的視窗
            window_kind = event.key() - Qt.Key.Key_1 + 1
            if self.center_points:
                center_x, center_y = random.choice(self.center_points)
                self.spawn_window(center_x, center_y, window_kind)
        elif event.key() == Qt.Key.Key_0:
            # 按0生成類型10的視窗
            if self.center_points:
                center_x, center_y = random.choice(self.center_points)
                self.spawn_window(center_x, center_y, 10)


def main():
    app = QApplication(sys.argv)
    effect = WindowEffect()
    effect.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
