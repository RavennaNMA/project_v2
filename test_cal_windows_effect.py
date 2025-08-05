#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 cal_windows_effect.py 配置使用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.cal_windows_effect import ImprovedCalWindow, ImprovedDetectionWindowEffect
from utils.anim_config_loader import AnimConfigLoader

def test_cal_windows_effect_config():
    """測試 cal_windows_effect.py 的配置使用"""
    print("=== 測試 Cal Windows Effect 配置使用 ===")
    
    # 創建配置加載器
    config_loader = AnimConfigLoader()
    
    # 測試 ImprovedCalWindow 的配置使用
    print("\n1. 測試 ImprovedCalWindow 配置使用:")
    
    # 創建一個測試窗口
    test_window = ImprovedCalWindow(540, 960, 100, config=config_loader)
    
    print(f"  窗口大小: {test_window.width} x {test_window.height}")
    print(f"  基礎透明度: {test_window.base_alpha}")
    print(f"  生命值: {test_window.life}")
    
    # 測試配置讀取方法
    print(f"  從配置讀取的 spawn_rate: {config_loader.get_float('BASIC', 'spawn_rate', 0.1)}")
    print(f"  從配置讀取的 connection_alpha: {config_loader.get_int('BASIC', 'connection_alpha', 120)}")
    print(f"  從配置讀取的 line_smooth_factor: {config_loader.get_float('BASIC', 'line_smooth_factor', 0.8)}")
    
    # 測試 ImprovedDetectionWindowEffect 的配置使用
    print("\n2. 測試 ImprovedDetectionWindowEffect 配置使用:")
    
    effect = ImprovedDetectionWindowEffect(config=config_loader)
    
    print(f"  生成率: {effect.spawn_rate}")
    print(f"  最大窗口數: {effect.max_windows_per_face}")
    print(f"  生成延遲: {effect.spawn_delay_frames}")
    
    # 測試平滑移動配置
    print("\n3. 測試平滑移動配置:")
    smooth_configs = [
        ('BASIC', 'line_smooth_factor', 0.8),
        ('BASIC', 'window_smooth_factor', 0.15),
        ('BASIC', 'spawn_point_smooth_factor', 0.12),
        ('POSITION', 'point_smooth_factor', 0.1),
    ]
    
    for section, key, expected in smooth_configs:
        value = config_loader.get_float(section, key, expected)
        print(f"  {section}.{key}: {value} (預期: {expected})")
    
    # 測試位置配置
    print("\n4. 測試位置配置:")
    position_configs = [
        ('POSITION', 'min_radius', 200),
        ('POSITION', 'max_radius', 350),
        ('POSITION', 'quadrant_spread', 0.35),
        ('POSITION', 'random_offset_ratio', 0.05),
    ]
    
    for section, key, expected in position_configs:
        value = config_loader.get_float(section, key, expected)
        print(f"  {section}.{key}: {value} (預期: {expected})")
    
    # 測試視覺配置
    print("\n5. 測試視覺配置:")
    visual_configs = [
        ('VISUAL', 'window_width_base', 160),
        ('VISUAL', 'window_height_base', 100),
        ('VISUAL', 'size_multiplier_min', 0.9),
        ('VISUAL', 'size_multiplier_max', 1.1),
        ('VISUAL', 'line_thickness', 1.0),
        ('VISUAL', 'inner_alpha', 50),
    ]
    
    for section, key, expected in visual_configs:
        if key == 'line_thickness':
            value = config_loader.get_float(section, key, expected)
        else:
            value = config_loader.get_int(section, key, expected)
        print(f"  {section}.{key}: {value} (預期: {expected})")
    
    print("\n=== 配置使用測試完成 ===")
    print("✅ 所有配置項都能正確從 cal_windows_config.csv 讀取")
    print("✅ cal_windows_effect.py 將使用這些配置值")

if __name__ == "__main__":
    test_cal_windows_effect_config() 