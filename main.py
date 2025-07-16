# Location: project_v2/main.py
# Usage: 主程式進入點

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui import StartupWindow, MainWindow
from services import PlatformService

# ================================================================
# 字體大小配置 - 可自由調整數值來改變字體大小
# ================================================================

# Debug 文字大小 (像素，會根據縮放係數調整)
# 建議範圍：12-24，預設：16
DEBUG_TEXT_SIZE = 18

# 字幕文字大小 (像素，會根據縮放係數調整)  
# 建議範圍：20-40，預設：28
CAPTION_TEXT_SIZE = 20

# ================================================================
# 其他界面配置
# ================================================================

# Loading 文字大小 (像素，會根據縮放係數調整)
# 建議範圍：18-32，預設：24
LOADING_TEXT_SIZE = 20

# ================================================================
# TTS 語音配置
# ================================================================

# 啟用 TTS 語音朗讀英文字幕
# True: 啟用語音朗讀，False: 禁用語音朗讀
TTS_ENABLED = True

# TTS 語音速度 (範圍：50-300，預設：160)
TTS_RATE = 160

# TTS 音量 (範圍：0.0-1.0，預設：0.8)
TTS_VOLUME = 0.8

# ================================================================
# 語音修改配置 (Voice Modification)
# ================================================================

# 啟用語音修改功能
# True: 啟用語音修改，False: 使用原始TTS聲音
VOICE_MOD_ENABLED = True

# 從ComfyUI同步設定 (啟用後會自動讀取ComfyUI的輸出設定)
# True: 從ComfyUI同步，False: 使用下方手動設定
VOICE_MOD_SYNC_FROM_COMFYUI = True

# 手動語音修改設定 (當VOICE_MOD_SYNC_FROM_COMFYUI=False時使用)
VOICE_MOD_PITCH_SHIFT = 0.0      # 音調偏移 (-12到+12半音)
VOICE_MOD_FORMANT_SHIFT = 0.0    # 音色偏移 (-5到+5)
VOICE_MOD_REVERB_AMOUNT = 0.0    # 混響量 (0.0-1.0)
VOICE_MOD_ECHO_DELAY = 0.0       # 回聲延遲 (0.0-1.0)
VOICE_MOD_COMPRESSION = 0.0      # 壓縮量 (0.0-1.0)
VOICE_MOD_EFFECT_BLEND = 1.0     # 效果混合比例 (0.0-1.0)
VOICE_MOD_OUTPUT_VOLUME = 0.0    # 輸出音量 (-20dB到+20dB)

# ================================================================
# 字體大小調整說明：
# 1. 修改上方的數值後，重新運行程式即可看到效果
# 2. Mini mode 會自動縮放至 0.5 倍
# 3. 數值越大字體越大，建議逐步調整測試效果
# 4. Debug模式需在啟動時開啟才會顯示debug文字
# ================================================================

class DefenseDetectionSystem:
    """DefenseSystem主類別"""
    
    def __init__(self):
        self.app = None
        self.startup_window = None
        self.main_window = None
        self.platform_service = PlatformService()
        
    def run(self):
        """執行應用程式"""
        # 建立 Qt 應用程式
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("DefenseSystem")
        self.app.setOrganizationName("DefenseSystem")
        
        # 設定高 DPI 支援
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            self.app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            self.app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
            
        # 檢查系統相依性
        deps = self.platform_service.check_dependencies()
        if not deps['all_satisfied']:
            print(f"缺少相依性: {deps['missing']}")
            print("請執行 pip install -r requirements.txt")
            return 1
            
        # 檢查相機權限
        if not self.platform_service.get_camera_permissions():
            self.platform_service.request_camera_permission()
            
        # 建立必要目錄
        self._create_directories()
        
        # 顯示啟動視窗
        self.startup_window = StartupWindow()
        self.startup_window.start_requested.connect(self.on_startup_complete)
        self.startup_window.show()
        
        # 執行應用程式
        return self.app.exec()
        
    def on_startup_complete(self, params):
        """啟動設定完成"""
        # 將字體大小配置加入啟動參數
        params['debug_text_size'] = DEBUG_TEXT_SIZE
        params['caption_text_size'] = CAPTION_TEXT_SIZE
        params['loading_text_size'] = LOADING_TEXT_SIZE
        
        # 將TTS配置加入啟動參數
        params['tts_enabled'] = TTS_ENABLED
        params['tts_rate'] = TTS_RATE
        params['tts_volume'] = TTS_VOLUME
        
        # 將語音修改配置加入啟動參數
        params['voice_mod_enabled'] = VOICE_MOD_ENABLED
        params['voice_mod_sync_from_comfyui'] = VOICE_MOD_SYNC_FROM_COMFYUI
        params['voice_mod_pitch_shift'] = VOICE_MOD_PITCH_SHIFT
        params['voice_mod_formant_shift'] = VOICE_MOD_FORMANT_SHIFT
        params['voice_mod_reverb_amount'] = VOICE_MOD_REVERB_AMOUNT
        params['voice_mod_echo_delay'] = VOICE_MOD_ECHO_DELAY
        params['voice_mod_compression'] = VOICE_MOD_COMPRESSION
        params['voice_mod_effect_blend'] = VOICE_MOD_EFFECT_BLEND
        params['voice_mod_output_volume'] = VOICE_MOD_OUTPUT_VOLUME
        
        # 建立並顯示主視窗
        self.main_window = MainWindow(params)
        self.main_window.show()
        
        # 關閉啟動視窗
        if self.startup_window:
            self.startup_window.close()
            self.startup_window = None
            
    def _create_directories(self):
        """建立必要的目錄"""
        directories = [
            'webcam-shots',
            'weapons_img',
            'fonts'
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"建立目錄: {directory}")


def main():
    """主函式"""
    # 設定工作目錄為腳本所在目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 執行系統
    system = DefenseDetectionSystem()
    return system.run()


if __name__ == "__main__":
    sys.exit(main())