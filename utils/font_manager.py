# Location: project_v2/utils/font_manager.py
# Usage: 字型管理器，處理中文字型載入

import os
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtCore import QObject


class FontManager(QObject):
    """字型管理器"""
    
    def __init__(self):
        super().__init__()
        self.font_loaded = False
        self.font_family = None
        # 暫時跳過自訂字型載入，直接使用系統字型
        # self.load_custom_font()
        self._use_system_font()
        
    def load_custom_font(self):
        """載入自訂字型"""
        try:
            # 嘗試多個路徑來找到字型檔案，優先使用 TTF 格式
            possible_paths = [
                os.path.join("fonts", "NotoSansTC-Regular.ttf"),
                os.path.join("fonts", "NotoSansCJKtc-Regular.otf"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "NotoSansTC-Regular.ttf"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "NotoSansCJKtc-Regular.otf"),
                os.path.join(os.getcwd(), "fonts", "NotoSansTC-Regular.ttf"),
                os.path.join(os.getcwd(), "fonts", "NotoSansCJKtc-Regular.otf")
            ]
            
            font_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    # 檢查檔案是否為有效的字型檔案
                    try:
                        with open(path, 'rb') as f:
                            header = f.read(4)
                            if header in [b'OTTO', b'\x00\x01\x00\x00', b'true', b'ttcf']:
                                font_path = path
                                print(f"找到有效字型檔案: {path}")
                                break
                    except:
                        continue
            
            if font_path:
                print(f"嘗試載入字型: {font_path}")
                
                # 檢查檔案是否可讀
                try:
                    with open(font_path, 'rb') as f:
                        header = f.read(4)
                        print(f"字型檔案頭部: {header.hex()}")
                except Exception as e:
                    print(f"無法讀取字型檔案: {e}")
                    return
                
                # 嘗試載入字型
                font_id = QFontDatabase.addApplicationFont(font_path)
                print(f"字型載入結果 ID: {font_id}")
                
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    print(f"可用字型家族: {families}")
                    if families:
                        self.font_family = families[0]
                        self.font_loaded = True
                        print(f"成功載入字型: {self.font_family}")
                    else:
                        print("無法取得字型家族名稱")
                else:
                    print(f"載入字型失敗: {font_path}")
                    
                    # 嘗試檢查系統字型
                    print("檢查系統可用字型...")
                    system_fonts = QFontDatabase.families()
                    chinese_fonts = [f for f in system_fonts if any(keyword in f.lower() for keyword in ['chinese', 'cjk', 'tc', 'sc', '中文', '黑體', '宋體', 'pingfang', 'noto'])]
                    print(f"系統中文字型: {chinese_fonts[:5]}")  # 只顯示前5個
            else:
                print(f"找不到有效的字型檔案，嘗試的路徑: {possible_paths}")
        except Exception as e:
            print(f"載入字型時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            self.font_loaded = False
            
    def get_font(self, size=12, bold=False):
        """取得字型"""
        if self.font_loaded and self.font_family:
            font = QFont(self.font_family)
        else:
            # 使用系統預設字型
            font = QFont()
            font.setFamily(self._get_system_font())
            
        font.setPointSize(size)
        font.setBold(bold)
        
        return font
        
    def _get_system_font(self):
        """取得系統預設中文字型"""
        import platform
        
        system = platform.system()
        if system == "Darwin":  # macOS
            return "PingFang TC"
        elif system == "Windows":
            return "Microsoft YaHei"
        else:  # Linux
            return "Noto Sans CJK TC"
            
    def get_available_fonts(self):
        """取得可用的中文字型列表"""
        chinese_fonts = []
        
        for family in QFontDatabase.families():
            # 檢查是否支援中文
            if any(char in family.lower() for char in ['chinese', 'cjk', 'tc', 'sc', '中文', '黑體', '宋體']):
                chinese_fonts.append(family)
                
        return chinese_fonts
        
    def _use_system_font(self):
        """使用系統中文字型，優先使用 Noto Sans TC"""
        try:
            system_fonts = QFontDatabase.families()
            print(f"系統可用字型數量: {len(system_fonts)}")
            
            # 優先使用 Noto Sans TC
            if "Noto Sans TC" in system_fonts:
                self.font_family = "Noto Sans TC"
                self.font_loaded = True
                print("使用 Noto Sans TC 字型")
                return
            
            # 如果沒有 Noto Sans TC，尋找其他中文字型
            chinese_fonts = [f for f in system_fonts if any(keyword in f.lower() for keyword in ['chinese', 'cjk', 'tc', 'sc', '中文', '黑體', '宋體', 'pingfang', 'noto'])]
            print(f"找到中文字型: {chinese_fonts[:5]}")  # 顯示前5個
            
            if chinese_fonts:
                self.font_family = chinese_fonts[0]
                self.font_loaded = True
                print(f"使用系統中文字型: {self.font_family}")
            else:
                # 最後 fallback 到系統預設字型
                self.font_family = self._get_system_font()
                self.font_loaded = True
                print(f"使用系統預設字型: {self.font_family}")
        except Exception as e:
            print(f"設定字型時發生錯誤: {e}")
            # 使用預設字型
            self.font_family = self._get_system_font()
            self.font_loaded = True