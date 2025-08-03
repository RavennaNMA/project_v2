# 科技感窗口效果 (Cal Windows Effect)

## 📖 概述

科技感窗口效果為檢測系統提供了炫酷的動態視覺元素，支援兩種模式：
- **檢測模式**：以人臉檢測框為中心生成科技窗口
- **獨立模式**：在 LLM 載入等場景下提供持續的科技感效果

## 🎯 主要特點

### ✅ 豐富的窗口類型
- 16 種不同的科技感窗口內容
- 條形圖、折線圖、矩陣顯示、雷達圖案等
- 每種窗口都有獨特的動畫效果

### ✅ 智能生命週期管理
- 窗口生命週期：80-150 幀
- 生成率：25% (檢測模式) / 30% (獨立模式)
- 自動清理過期窗口

### ✅ 雙模式支援
- **檢測模式**：圍繞每個檢測到的人臉生成 3-4 個中心點
- **獨立模式**：在屏幕中心區域生成 2 個中心點，不依賴人臉檢測

### ✅ 同步閃爍效果
- 檢測框閃爍時，相關窗口同步閃爍
- 保持視覺效果的一致性

## 🚀 使用方法

### 基本整合

```python
from ui.detection_overlay import DetectionOverlay

# 創建檢測覆蓋層
overlay = DetectionOverlay()

# 正常的人臉檢測更新（會自動生成窗口效果）
overlay.update_faces(detected_faces)

# 在 OpenCV 幀上繪製
frame = overlay.draw_on_frame(frame)
```

### 獨立模式（LLM 載入效果）

```python
# 啟用獨立模式（用於 LLM 載入時）
overlay.enable_standalone_window_effect(True)

# 持續更新窗口效果（不需要人臉檢測）
while llm_loading:
    overlay.update_standalone_windows()
    frame = overlay.draw_on_frame(frame)
    cv2.imshow('Window', frame)
    cv2.waitKey(16)

# 載入完成後禁用獨立模式
overlay.enable_standalone_window_effect(False)
```

### 進階控制

```python
# 清除檢測框但保留獨立模式窗口
overlay.clear_detections()

# 清除所有效果（包括獨立模式）
overlay.clear_all_effects()

# 獲取當前窗口數量
total_windows = overlay.window_effect.get_total_window_count()

# 檢查獨立模式狀態
is_standalone = overlay.window_effect.standalone_mode
```

## ⚙️ 配置參數

### 窗口生成配置
```python
SPAWN_RATE = 0.25           # 檢測模式生成率 (25%)
STANDALONE_SPAWN_RATE = 0.3 # 獨立模式生成率 (30%)
MIN_LIFE = 80               # 最小生命週期 (幀)
MAX_LIFE = 150              # 最大生命週期 (幀)
```

### 窗口尺寸
```python
WINDOW_WIDTH_DEFAULT = 320   # 寬度 (比原版 *2)
WINDOW_HEIGHT_DEFAULT = 200  # 高度 (比原版 *2)
```

### 中心點配置
```python
CENTER_POINTS_PER_FACE = 4      # 每個人臉的中心點數量 (3-4 個隨機)
STANDALONE_CENTER_COUNT = 2     # 獨立模式中心點數量
CENTER_SPREAD = 80              # 檢測模式擴散範圍
STANDALONE_CENTER_SPREAD = 200  # 獨立模式擴散範圍
```

## 🎨 16 種窗口類型

1. **條形圖** - 動態數據條
2. **折線圖** - 帶點的連線圖
3. **曲線圖** - 帶基準線的曲線
4. **矩陣顯示** - 數字矩陣動畫
5. **幾何圖案** - 三角形組合
6. **網格圖案** - 隨機填充網格
7. **示波器** - 水平波形顯示
8. **雷達圖案** - 圓形掃描效果
9. **複雜形狀** - 旋轉多邊形
10. **十字準星** - 動態準星系統
11. **鑽石形狀** - 幾何鑽石組合
12. **等級指示器** - 垂直進度條
13. **進度條** - 水平填充條
14. **垂直示波器** - 垂直波形
15. **軌道圖案** - 圓形軌道動畫
16. **堆疊條形圖** - 多重數據條

## 🧪 測試工具

使用測試程序來體驗效果：

```bash
cd ui
python cal_windows_test.py
```

選擇測試模式：
- **模式 1**：獨立模式測試（模擬 LLM 載入）
- **模式 2**：人臉檢測模式測試

### 測試控制鍵
- `q` - 退出
- `s` - 切換獨立模式
- `f` - 切換人臉檢測（僅模式 2）

## 📊 性能特點

- **高效繪製**：直接使用 OpenCV 繪製，避免 PyQt 轉換開銷
- **智能管理**：自動管理窗口生命週期，防止記憶體洩漏
- **可調參數**：所有關鍵參數都可配置
- **低耦合設計**：模組化設計，易於整合和修改

## 🔧 調整建議

### 想要更多同時窗口？
```python
# 增加生成率
SPAWN_RATE = 0.4

# 延長生命週期
MIN_LIFE = 100
MAX_LIFE = 200
```

### 想要更快的動畫？
```python
# 縮短生命週期
MIN_LIFE = 50
MAX_LIFE = 100

# 提高生成率
SPAWN_RATE = 0.5
```

### 想要更密集的分布？
```python
# 增加中心點數量
CENTER_POINTS_PER_FACE = 6

# 縮小擴散範圍
CENTER_SPREAD = 60
```

## 🎯 集成示例

```python
class YourMainApp:
    def __init__(self):
        self.detection_overlay = DetectionOverlay()
        self.llm_loading = False
    
    def start_llm_loading(self):
        """開始 LLM 載入"""
        self.llm_loading = True
        self.detection_overlay.enable_standalone_window_effect(True)
    
    def stop_llm_loading(self):
        """結束 LLM 載入"""
        self.llm_loading = False
        self.detection_overlay.enable_standalone_window_effect(False)
    
    def update_frame(self, frame, faces):
        """更新畫面"""
        if faces:
            self.detection_overlay.update_faces(faces)
        elif self.llm_loading:
            self.detection_overlay.update_standalone_windows()
        
        return self.detection_overlay.draw_on_frame(frame)
```

現在您可以享受更豐富、更炫酷的科技感視覺效果了！🚀 