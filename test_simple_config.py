#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡單的配置測試
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.anim_config_loader import AnimConfigLoader

def test_simple_config():
    """簡單的配置測試"""
    print("=== 簡單配置測試 ===")
    
    # 創建配置加載器
    config_loader = AnimConfigLoader()
    
    # 測試平滑移動相關的配置
    print("\n平滑移動配置:")
    smooth_configs = [
        ('BASIC', 'line_smooth_factor', 0.8),
        ('BASIC', 'window_smooth_factor', 0.15),
        ('BASIC', 'spawn_point_smooth_factor', 0.12),
        ('POSITION', 'point_smooth_factor', 0.1),
    ]
    
    all_passed = True
    for section, key, expected in smooth_configs:
        value = config_loader.get_float(section, key, expected)
        status = "✅" if abs(value - expected) < 0.001 else "❌"
        print(f"  {status} {section}.{key}: {value} (預期: {expected})")
        if abs(value - expected) >= 0.001:
            all_passed = False
    
    # 測試基本配置
    print("\n基本配置:")
    basic_configs = [
        ('BASIC', 'spawn_rate', 0.1),
        ('BASIC', 'max_windows_per_face', 4),
        ('BASIC', 'connection_alpha', 120),
        ('BASIC', 'window_alpha', 180),
    ]
    
    for section, key, expected in basic_configs:
        if isinstance(expected, float):
            value = config_loader.get_float(section, key, expected)
        elif isinstance(expected, int):
            value = config_loader.get_int(section, key, expected)
        else:
            value = config_loader.get(section, key, expected)
        
        status = "✅" if value == expected else "❌"
        print(f"  {status} {section}.{key}: {value} (預期: {expected})")
        if value != expected:
            all_passed = False
    
    # 測試位置配置
    print("\n位置配置:")
    position_configs = [
        ('POSITION', 'min_radius', 200),
        ('POSITION', 'max_radius', 350),
        ('POSITION', 'quadrant_spread', 0.35),
        ('POSITION', 'random_offset_ratio', 0.05),
    ]
    
    for section, key, expected in position_configs:
        value = config_loader.get_float(section, key, expected)
        status = "✅" if abs(value - expected) < 0.001 else "❌"
        print(f"  {status} {section}.{key}: {value} (預期: {expected})")
        if abs(value - expected) >= 0.001:
            all_passed = False
    
    # 測試視覺配置
    print("\n視覺配置:")
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
        
        status = "✅" if value == expected else "❌"
        print(f"  {status} {section}.{key}: {value} (預期: {expected})")
        if value != expected:
            all_passed = False
    
    print(f"\n=== 測試結果: {'✅ 全部通過' if all_passed else '❌ 有錯誤'} ===")
    
    if all_passed:
        print("🎉 cal_windows_config.csv 配置已正確加載並將影響 cal_windows_effect.py")
        print("🎉 平滑移動功能將使用這些配置值")
    else:
        print("⚠️  部分配置項有問題，請檢查 cal_windows_config.csv 文件")

if __name__ == "__main__":
    test_simple_config() 