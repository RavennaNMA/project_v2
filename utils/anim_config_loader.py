# Location: project_v2/utils/anim_config_loader.py
# Usage: 動畫配置文件加載器

import os
import csv
from typing import Dict, Any, Union


class AnimConfigLoader:
    """動畫配置文件加載器 - 用於讀取 anim_config.csv"""
    
    def __init__(self, config_file='config/anim_config.csv'):
        self.config_file = config_file
        self.config = {}
        self.load_config()
        
        # 載入 cal windows 配置
        self.cal_windows_config = {}
        self.load_cal_windows_config()
    
    def load_config(self):
        """載入配置文件"""
        if not os.path.exists(self.config_file):
            print(f"動畫配置文件不存在: {self.config_file}，使用默認設定")
            self.use_defaults()
            return
        
        try:
            config_dict = {}
            
            # 先过滤掉注释行，然后创建DictReader
            lines = []
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        lines.append(line)
            
            # 确保有标题行
            if not lines:
                raise ValueError("配置文件为空或只有注释")
            
            # 使用StringIO创建CSV reader
            from io import StringIO
            csv_content = '\n'.join(lines)
            csv_file = StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            for row in reader:
                # 跳過空行
                if not row.get('Section'):
                    continue
                
                section = row['Section'].strip()
                key = row['Key'].strip()
                value = row['Value'].strip()
                

                
                # 創建嵌套字典結構
                if section not in config_dict:
                    config_dict[section] = {}
                
                # 解析值的類型
                config_dict[section][key] = self._parse_value(value)
            
            self.config = config_dict
            print(f"動畫配置已加載，共 {len(self.config)} 個區段")
            
            # 顯示關鍵配置
            self._print_key_settings()
                
        except Exception as e:
            print(f"加載動畫配置文件失敗: {e}，使用默認設定")
            self.use_defaults()
    
    def load_cal_windows_config(self):
        """載入 cal windows 配置"""
        cal_windows_config_file = 'config/cal_windows_config.csv'
        
        if not os.path.exists(cal_windows_config_file):
            print(f"Cal Windows 配置文件不存在: {cal_windows_config_file}，使用默認設定")
            self.cal_windows_config = self._get_default_cal_windows_config()
            return
        
        try:
            config_dict = {}
            
            # 先过滤掉注释行，然后创建DictReader
            lines = []
            with open(cal_windows_config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        lines.append(line)
            
            # 确保有标题行
            if not lines:
                raise ValueError("Cal Windows 配置文件为空或只有注释")
            
            # 使用StringIO创建CSV reader
            from io import StringIO
            csv_content = '\n'.join(lines)
            csv_file = StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            for row in reader:
                # 跳過空行
                if not row.get('SECTION'):
                    continue
                
                section = row['SECTION'].strip()
                key = row['KEY'].strip()
                value = row['VALUE'].strip()
                
                # 創建嵌套字典結構
                if section not in config_dict:
                    config_dict[section] = {}
                
                # 解析值的類型
                config_dict[section][key] = self._parse_value(value)
            
            self.cal_windows_config = config_dict
            print(f"Cal Windows 配置已加載，共 {len(self.cal_windows_config)} 個區段")
                
        except Exception as e:
            print(f"加載 Cal Windows 配置文件失敗: {e}，使用默認設定")
            self.cal_windows_config = self._get_default_cal_windows_config()
    
    def _get_default_cal_windows_config(self):
        """獲取默認的 cal windows 配置"""
        return {
            'BASIC': {
                'enabled': True,
                'spawn_rate': 0.1,
                'max_windows_per_face': 4,
                'spawn_delay_frames': 30,
                'min_life': 200,
                'max_life': 400,
                'connection_alpha': 120,
                'window_alpha': 180,
                'stable_connection_lines': True,
                'line_smooth_factor': 0.8,
                'window_smooth_factor': 0.15,
                'spawn_point_smooth_factor': 0.12,
                'cal_window_fade_frames': 10,
                'detect_frame_fade_frames': 5
            },
            'POSITION': {
                'min_radius': 200,
                'max_radius': 350,
                'quadrant_spread': 0.35,
                'random_offset_ratio': 0.05,
                'point_smooth_factor': 0.1
            },
            'VISUAL': {
                'window_width_base': 160,
                'window_height_base': 100,
                'size_multiplier_min': 0.9,
                'size_multiplier_max': 1.1,
                'line_thickness': 1,
                'inner_alpha': 50
            },
            'ANIMATION': {
                'content_animation_speed': 0.1,
                'frame_count_global': True,
                'window_type_sequences': True
            }
        }
    
    def _parse_value(self, value: str) -> Union[str, int, float, bool]:
        """解析配置值的類型"""
        # 布爾值
        if value.lower() in ['true', 'yes', '1', 'on']:
            return True
        elif value.lower() in ['false', 'no', '0', 'off']:
            return False
        
        # 數字
        try:
            # 先嘗試整數
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            pass
        
        # 字符串
        return value
    
    def _print_key_settings(self):
        """打印關鍵設定"""
        print("動畫關鍵設定:")
        
        # 顯示基本設定
        if 'BASIC' in self.config:
            print("  基本設定:")
            basic = self.config['BASIC']
            for key in ['position_smooth', 'state1_duration', 'state2_duration', 
                       'state3_duration', 'state4_duration', 'frame_size_multiplier']:
                if key in basic:
                    print(f"    {key}: {basic[key]}")
        
        # 顯示視覺設定
        if 'VISUAL' in self.config:
            print("  視覺設定:")
            visual = self.config['VISUAL']
            for key in ['color_r', 'color_g', 'color_b', 'flicker_probability']:
                if key in visual:
                    print(f"    {key}: {visual[key]}")
    
    def use_defaults(self):
        """使用默認配置"""
        self.config = {
            'BASIC': {
                'position_smooth': 0.03,
                'state1_duration': 200,
                'state2_duration': 200,
                'state3_duration': 60,
                'state4_duration': 240,
                'frame_size_multiplier': 1.3
            },
            'STATE1': {
                'outside_smooth': 0.05,
                'corner_length_ratio': 0.07,
                'line_thickness': 1
            },
            'STATE2': {
                'outside_smooth': 0.05,
                'inner_smooth': 0.04,
                'inner_alpha': 50,
                'inner_size_ratio': 0.9,
                'corner_length_ratio': 0.07,
                'line_thickness': 1
            },
            'STATE3': {
                'outside_smooth': 0.05,
                'inner_smooth': 0.04,
                'cross_start_smooth': 0.04,
                'cross_length_ratio_h': 0.59,
                'cross_length_ratio_w': 0.55,
                'corner_length_ratio': 0.07,
                'line_thickness': 1.25,
                'inner_alpha': 50,
                'inner_size_ratio': 0.9
            },
            'STATE4': {
                'outside_smooth': 0.05,
                'inner_smooth': 0.04,
                'cross_start_smooth': 0.04,
                'cross_end_smooth': 0.05,
                'cross_length_ratio_h': 0.59,
                'cross_length_ratio_w': 0.55,
                'corner_length_ratio': 0.07,
                'line_thickness': 1.5
            },
            'VISUAL': {
                'color_r': 255,
                'color_g': 255,
                'color_b': 255,
                'alpha': 200,
                'flicker_probability': 0.2
            }
        }
        print("使用動畫默認配置")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """獲取配置值 - 優先從 cal_windows_config 讀取"""
        # 優先從 cal_windows_config 讀取
        if section in self.cal_windows_config and key in self.cal_windows_config[section]:
            return self.cal_windows_config[section][key]
        # 如果 cal_windows_config 中沒有，則從主配置讀取
        return self.config.get(section, {}).get(key, default)
    
    def get_str(self, section: str, key: str, default: str = '') -> str:
        """獲取字符串配置值"""
        value = self.get(section, key, default)
        return str(value)
    
    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """獲取整數配置值"""
        value = self.get(section, key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """獲取浮點數配置值"""
        value = self.get(section, key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """獲取布爾配置值"""
        value = self.get(section, key, default)
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ['true', 'yes', '1', 'on']
        else:
            return bool(value)
    
    def reload_config(self):
        """重新載入配置文件"""
        self.load_config()
        self.load_cal_windows_config()
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """獲取整個區段的配置"""
        return self.config.get(section, {})
    
    def validate_config(self) -> Dict[str, str]:
        """驗證配置的有效性"""
        errors = {}
        
        # 檢查基本設定
        basic = self.get_section('BASIC')
        
        position_smooth = basic.get('position_smooth', 0.08)
        if not (0.0 <= position_smooth <= 1.0):
            errors['position_smooth'] = f"位置平滑度必須在0.0-1.0之間，當前值: {position_smooth}"
        
        frame_multiplier = basic.get('frame_size_multiplier', 1.5)
        if not (0.5 <= frame_multiplier <= 5.0):
            errors['frame_size_multiplier'] = f"框放大倍數必須在0.5-5.0之間，當前值: {frame_multiplier}"
        
        # 檢查持續時間
        for state in ['state1_duration', 'state2_duration', 'state3_duration', 'state4_duration']:
            duration = basic.get(state, 60)
            if not (1 <= duration <= 1000):
                errors[state] = f"{state}必須在1-1000之間，當前值: {duration}"
        
        # 檢查視覺設定
        visual = self.get_section('VISUAL')
        
        for color in ['color_r', 'color_g', 'color_b']:
            color_value = visual.get(color, 255)
            if not (0 <= color_value <= 255):
                errors[color] = f"{color}必須在0-255之間，當前值: {color_value}"
        
        flicker_prob = visual.get('flicker_probability', 0.2)
        if not (0.0 <= flicker_prob <= 1.0):
            errors['flicker_probability'] = f"閃爍機率必須在0.0-1.0之間，當前值: {flicker_prob}"
        
        return errors
    
    def get_total_duration(self) -> int:
        """獲取總動畫持續時間"""
        basic = self.get_section('BASIC')
        return (basic.get('state1_duration', 60) + 
                basic.get('state2_duration', 60) + 
                basic.get('state3_duration', 60) + 
                basic.get('state4_duration', 60))
    
    def get_color_bgr(self) -> tuple:
        """獲取BGR格式的顏色 (OpenCV格式)"""
        visual = self.get_section('VISUAL')
        r = visual.get('color_r', 255)
        g = visual.get('color_g', 255)
        b = visual.get('color_b', 255)
        return (b, g, r)  # OpenCV使用BGR格式 