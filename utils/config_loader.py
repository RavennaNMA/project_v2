# Location: project_v2/utils/config_loader.py
# Usage: 配置檔案載入器，處理 CSV 設定檔

import csv
import os
from PyQt6.QtCore import QObject


class ConfigLoader(QObject):
    """配置檔案載入器"""
    
    def __init__(self):
        super().__init__()
        self.period_config = {}
        self.weapon_config = {}
        self.debug_config = {}  # 💡 新增：調試配置
        
    def load_period_config(self):
        """載入時間設定"""
        config_path = "config/period_config.csv"
        
        if not os.path.exists(config_path):
            print(f"找不到設定檔: {config_path}")
            return self._get_default_period_config()
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    param_name = row['參數名稱']
                    default_value = float(row['預設值'])
                    self.period_config[param_name] = default_value
                    
            # 載入時間設定完成，移除冗餘調試輸出
            return self.period_config
            
        except Exception as e:
            print(f"載入時間設定失敗: {e}")
            return self._get_default_period_config()
            
    def load_weapon_config(self):
        """載入武器設定"""
        config_path = "config/weapon_config.csv"
        
        if not os.path.exists(config_path):
            print(f"找不到設定檔: {config_path}")
            return self._get_default_weapon_config()
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    weapon_id = row['武器編號']
                    
                    # 安全地解析整數值
                    def safe_int(value, default=0):
                        try:
                            return int(value) if value and value.isdigit() else default
                        except:
                            return default
                    
                    # 安全地解析浮點數值
                    def safe_float(value, default=1.0):
                        try:
                            return float(value) if value else default
                        except:
                            return default
                    
                    # 處理腳位控制時間（毫秒）
                    wait_before = safe_int(row.get('腳位控制前的延遲時間', '0'))
                    high_time = safe_int(row.get('腳位為 HIGH 的維持時間', '1000'))
                    wait_after = safe_int(row.get('腳位降回 LOW 後的等待時間', '0'))
                    
                    # 處理圖片顯示時間（秒）
                    image_fade_in = safe_float(row.get('圖片淡入所需時間', '1.0'))
                    image_display = safe_float(row.get('圖片顯示的時間', '3.0'))
                    image_fade_out = safe_float(row.get(' 圖片淡出所需時間', '1.0'))  # 注意前面有空格
                    
                    # 處理腳位
                    pin_str = row.get('對應腳位', '')
                    pin = safe_int(pin_str) if pin_str else None
                    
                    self.weapon_config[weapon_id] = {
                        'id': weapon_id,
                        'name': row['顯示名稱'],
                        'pin': pin,
                        'image_path': row.get('圖片路徑 (weapons_img/下)', 'default.png'),
                        'wait_before': wait_before,
                        'high_time': high_time,
                        'wait_after': wait_after,
                        'image_fade_in': image_fade_in,
                        'image_display': image_display,
                        'image_fade_out': image_fade_out
                    }
                    
            # 載入武器設定完成，移除冗餘調試輸出
            return self.weapon_config
            
        except Exception as e:
            print(f"載入武器設定失敗: {e}")
            print(f"錯誤詳情: {type(e).__name__}: {str(e)}")
            return self._get_default_weapon_config()
            
    def get_weapon_list(self):
        """取得武器列表（供 AI 使用）"""
        if not self.weapon_config:
            self.load_weapon_config()
            
        weapon_list = []
        for weapon_id, info in self.weapon_config.items():
            weapon_list.append({
                'id': weapon_id,
                'name': info['name']
            })
            
        return weapon_list
        
    def load_debug_config(self):
        """💡 新增：載入調試模式設定"""
        config_path = "config/nollmdebug.csv"
        
        if not os.path.exists(config_path):
            print(f"找不到調試設定檔: {config_path}")
            return self._get_default_debug_config()
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    param_name = row['參數名稱']
                    value = row['預設值']
                    
                    # 處理不同類型的值
                    if param_name in ['debug_arduino_enabled', 'debug_verbose']:
                        # 布林值
                        self.debug_config[param_name] = value.lower() in ['true', '1', 'yes']
                    elif param_name in ['debug_weapon_1', 'debug_weapon_2', 'debug_weapon_3']:
                        # 武器編號字串
                        self.debug_config[param_name] = value.strip()
                    else:
                        # 字串值（字幕內容）
                        self.debug_config[param_name] = value
                    
            # 載入調試設定完成，移除冗餘調試輸出
            return self.debug_config
            
        except Exception as e:
            print(f"載入調試設定失敗: {e}")
            return self._get_default_debug_config()
            
    def get_debug_response(self):
        """💡 新增：取得調試模式的預設回應"""
        if not self.debug_config:
            self.load_debug_config()
            
        # 組合武器列表
        weapons = []
        for i in range(1, 4):  # weapon_1, weapon_2, weapon_3
            weapon_key = f'debug_weapon_{i}'
            if weapon_key in self.debug_config and self.debug_config[weapon_key]:
                weapons.append(self.debug_config[weapon_key])
        
        return {
            'caption': self.debug_config.get('debug_caption_en', 'Emergency defense protocol activated.'),
            'caption_tc': self.debug_config.get('debug_caption_tc', '緊急防禦協議啟動。'),
            'weapons': weapons
        }
        
    def _get_default_period_config(self):
        """預設時間設定"""
        return {
            'detection_sensitivity': 0.75,
            'detect_duration': 3.0,
            'detect_area_ratio': 0.8,
            'detect_anim_stage1_duration': 0.5,
            'detect_anim_stage2_duration': 0.5,
            'detect_anim_stage3_duration': 0.2,
            'detect_anim_stage4_duration': 0.3,
            'llm_response_timeout': 10.0,
            'screenshot_fade_in': 1.0,
            'screenshot_display': 5.0,
            'screenshot_fade_out': 1.0,
            'caption_typing_speed': 80,
            'caption_max_chars_per_line': 65,
            'caption_chinese_char_weight': 1.8,
            'caption_wait_after': 2.0,
            'weapon_fade_in': 1.0,
            'weapon_display': 3.0,
            'weapon_fade_out': 1.0,
            'weapon_switch_delay': 0.5,
            'shot_to_weapon_transition': 2.0,
            'image_switch_wait': 1.0,
            'cooldown_time': 3.0
        }
        
    def _get_default_weapon_config(self):
        """預設武器設定"""
        return {
            '01': {
                'id': '01',
                'name': '鐵鎚',
                'pin': 2,
                'image_path': 'hammer.png',
                'wait_before': 0,
                'high_time': 1000,
                'wait_after': 500,
                'image_fade_in': 1.0,
                'image_display': 3.0,
                'image_fade_out': 1.0
            },
            '02': {
                'id': '02',
                'name': '閃光燈',
                'pin': 3,
                'image_path': 'flashlight.png',
                'wait_before': 0,
                'high_time': 800,
                'wait_after': 300,
                'image_fade_in': 1.0,
                'image_display': 3.0,
                'image_fade_out': 1.0
            }
        }
        
    def _get_default_debug_config(self):
        """💡 新增：預設調試設定"""
        return {
            'debug_caption_en': 'Emergency defense protocol activated. Scanning for threats.',
            'debug_caption_tc': '緊急防禦協議啟動。正在掃描威脅。',
            'debug_weapon_1': '01',
            'debug_weapon_2': '02', 
            'debug_weapon_3': '03',
            'debug_arduino_enabled': True,
            'debug_verbose': True
        }
        
    def save_period_config(self):
        """儲存時間設定"""
        config_path = "config/period_config.csv"
        
        try:
            with open(config_path, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['中文名稱', '參數名稱', '預設值', '說明']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                
                # 寫入各項設定
                settings = [
                    ('偵測持續時間', 'detect_duration', 3.0, '人臉需持續偵測多久才觸發'),
                    ('截圖淡入時間', 'screenshot_fade_in', 1.0, '截圖淡入效果時間'),
                    ('截圖顯示時間', 'screenshot_display', 5.0, '截圖持續顯示時間'),
                    ('截圖淡出時間', 'screenshot_fade_out', 1.0, '截圖淡出效果時間'),
                    ('打字速度', 'caption_typing_speed', 80, '字幕打字機效果速度(毫秒/字)'),
                    ('武器淡入時間', 'weapon_fade_in', 1.0, '武器圖片淡入時間'),
                    ('武器顯示時間', 'weapon_display', 3.0, '武器圖片顯示時間'),
                    ('武器淡出時間', 'weapon_fade_out', 1.0, '武器圖片淡出時間'),
                    ('冷卻時間', 'cooldown_time', 3.0, '系統重置後的等待時間')
                ]
                
                for name_tc, param, value, desc in settings:
                    writer.writerow({
                        '中文名稱': name_tc,
                        '參數名稱': param,
                        '預設值': value,
                        '說明': desc
                    })
                    
            print(f"已建立預設設定檔: {config_path}")
            
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")