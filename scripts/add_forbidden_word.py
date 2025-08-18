#!/usr/bin/env python3
"""
快速添加禁用詞語的腳本
使用方法: python scripts/add_forbidden_word.py "不想要的詞語"
"""

import sys
import os

def add_forbidden_word(word):
    """添加禁用詞語到配置文件"""
    config_file = "config/forbidden_words_config.txt"
    
    if not word.strip():
        print("錯誤: 詞語不能為空")
        return False
    
    try:
        # 檢查詞語是否已存在
        existing_words = []
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                existing_words = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if word in existing_words:
            print(f"詞語 '{word}' 已存在於禁用列表中")
            return True
        
        # 添加新詞語
        with open(config_file, 'a', encoding='utf-8') as f:
            f.write(f"\n# 用戶添加於 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{word}\n")
        
        print(f"成功添加禁用詞語: '{word}'")
        print(f"重新啟動程式後生效")
        return True
        
    except Exception as e:
        print(f"添加禁用詞語失敗: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("使用方法: python scripts/add_forbidden_word.py '不想要的詞語'")
        print("例如: python scripts/add_forbidden_word.py 'fuck'")
        print("例如: python scripts/add_forbidden_word.py '\\\\bType\\\\b'  # 正則表達式")
        sys.exit(1)
    
    word = sys.argv[1]
    add_forbidden_word(word)

if __name__ == "__main__":
    main()
