# Location: project_v2/ui/caption_widget.py
# Usage: 字幕顯示元件，支援單語和雙語顯示，包含打字機效果和TTS即時同步
#  新功能：智能句子結尾自動完成，解決TTS接近句末時的卡頓問題
# 特點：
# - 88%完成時自動顯示剩餘文字（平衡設定）
# - 80%開始1.6倍適度加速（溫和但有效）
# - 83-88%時適度推進避免卡頓（平衡閾值）
# - 允許超前12%以避免明顯卡頓

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QObject
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QFontMetrics
from utils.font_manager import FontManager
import re
import time


class CaptionWidget(QWidget):
    """字幕顯示元件 - 優化的TTS同步版本"""
    
    typing_complete = pyqtSignal()
    tc_typing_complete = pyqtSignal()
    en_typing_complete = pyqtSignal()
    
    def __init__(self, parent=None, scale_factor=1.0, font_size=28):
        super().__init__(parent)
        self.scale_factor = scale_factor
        self.full_text = ""
        self.current_text = ""
        self.current_index = 0
        self.is_showing = False
        
        # 雙語模式相關
        self.is_bilingual_mode = False
        self.tc_text = ""
        self.en_text = ""
        self.tc_current_text = ""
        self.en_current_text = ""
        self.tc_index = 0
        self.en_index = 0
        self._tc_completed = False
        self._en_completed = False
        
        # 統一的顯示計時器 - 簡化邏輯
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self._update_display)
        
        # TTS同步
        self.tts_sync_enabled = False
        self.tts_target_position = 0
        self.last_tts_update_time = 0
        
        # 句子同步（簡單有效的解決方案）
        self.sentence_sync_mode = False  # 是否啟用句子同步模式
        self.tc_sentences = []  # 中文句子列表
        self.en_sentences = []  # 英文句子列表
        self.current_sentence_index = 0  # 當前句子索引
        
        # 配置
        self.auto_complete_threshold = 0.88  # xx%完成時自動顯示剩餘文字
        self.acceleration_threshold = 0.70   # 80%開始加速
        self.acceleration_multiplier = 1.5   # 加速倍數
        self.push_completion_threshold = 0.90  # 85%時強制推進完成
        
        # 字幕位置
        self.target_position_ratio = 0.97  # 字幕顯示位置

        
        # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        
        # 字型設定 
        base_font_size = int(font_size * scale_factor)
        from utils.font_manager import FontManager
        self.font_manager = FontManager()
        self.caption_font = self.font_manager.get_font(base_font_size)
        
        # 文字邊距
        self.padding = 20
        self.line_spacing = 10
        
        # 嘗試從配置文件載入設定
        self._load_wrapping_config()
        
        # 隱藏控制項
        self.hide()
        
    def _load_wrapping_config(self):
        """從配置文件載入換行設定"""
        try:
            from utils.config_loader import ConfigLoader
            config_loader = ConfigLoader()
            config = config_loader.load_period_config()
            
            # 載入字符限制設定 - 調整為更平衡的設定
            self.max_chars_per_line = config.get('caption_max_chars_per_line', 80)
            self.chinese_char_weight = config.get('caption_chinese_char_weight', 1.8)
            
            print(f"載入字幕換行設定: 每行{self.max_chars_per_line}字符, 中文權重{self.chinese_char_weight}")
        except Exception as e:
            print(f"載入換行配置失敗: {e}, 使用預設值")
            # 使用更平衡的預設值
            self.max_chars_per_line = 65
            self.chinese_char_weight = 1.2
        
    def show_caption(self, text, typing_speed=80):
        """顯示單語字幕 - 優化版本"""
        print(f"🎬 show_caption 被調用:")
        print(f"   文字長度: {len(text)}")
        print(f"   打字速度: {typing_speed}ms")
        
        self.full_text = text
        self.current_text = ""
        self.current_index = 0
        self.is_showing = True
        self.is_bilingual_mode = False
        self._typing_completed = False  # 重置完成標誌
        self._first_update_logged = False  # 重置調試標誌
        
        # 確保元件可見
        self.show()
        self.raise_()  # 置於最上層
        
        # 停止現有計時器
        if self.display_timer.isActive():
            self.display_timer.stop()
        
        # 使用統一的顯示機制
        if not self.tts_sync_enabled:
            # 修復：允許更快的打字速度，降低最小間隔限制
            interval = max(int(typing_speed), 5)  # 最少5ms間隔
            self.display_timer.start(interval)
            print(f" 啟動字幕顯示計時器，間隔: {interval}ms")
            print(f" 計時器狀態: {self.display_timer.isActive()}")
        else:
            # TTS同步模式使用固定的快速更新頻率
            self.display_timer.start(16)  # 60fps 更新頻率
            print(f"啟動TTS同步計時器，60fps更新")
        
        # 立即觸發一次更新
        self.update()
        
    def show_bilingual_caption(self, tc_text, en_text, typing_speed=80):
        """顯示雙語字幕 - 優化版本"""
        print(f"🌐 show_bilingual_caption 被調用:")
        print(f"   中文長度: {len(tc_text)}")
        print(f"   英文長度: {len(en_text)}")
        print(f"   打字速度: {typing_speed}ms")
        
        self.is_bilingual_mode = True
        self.tc_text = tc_text
        self.en_text = en_text
        
        # 重置狀態
        self.tc_current_text = ""
        self.en_current_text = ""
        self.tc_index = 0
        self.en_index = 0
        self._tc_completed = False
        self._en_completed = False
        self._typing_completed = False  # 重置完成標誌
        self._first_update_logged = False  # 重置調試標誌
        self.current_segment_index = 0  # 重置分段索引
        self.is_showing = True
        
        # 確保元件可見
        self.show()
        self.raise_()  # 置於最上層
        
        # 停止現有計時器
        if self.display_timer.isActive():
            self.display_timer.stop()
        
        # 使用統一的顯示機制
        if not self.tts_sync_enabled:
            # 修復：允許更快的打字速度，降低最小間隔限制
            interval = max(int(typing_speed), 5)  # 最少5ms間隔
            self.display_timer.start(interval)
            print(f" 雙語字幕顯示計時器，間隔: {interval}ms")
            print(f"   計時器狀態: {self.display_timer.isActive()}")
        else:
            self.display_timer.start(16)  # 60fps 更新頻率
            print(f" 啟動TTS同步計時器，60fps更新")
        
        # 立即觸發一次更新
        self.update()
        
    # 新增調試方法
    def debug_widget_state(self):
        """調試元件狀態"""
        print(f"🔍 字幕元件調試信息:")
        print(f"   可見: {self.isVisible()}")
        print(f"   位置: {self.pos()}")
        print(f"   大小: {self.size()}")
        print(f"   父元件: {self.parent()}")
        print(f"   計時器活動: {self.display_timer.isActive()}")
        print(f"   顯示中: {self.is_showing}")
        print(f"   當前文字長度: {len(self.current_text) if hasattr(self, 'current_text') else 0}")
        
    def enable_tts_sync(self, tts_text, tts_rate_wpm=140):
        """啟用TTS同步模式 - 簡化版本"""
        self.tts_sync_enabled = True
        self.tts_text = tts_text
        self.tts_target_position = 0
        self.last_tts_update_time = time.time()
        
        # 如果計時器已經在運行，重新配置為TTS同步模式
        if self.display_timer.isActive():
            self.display_timer.stop()
            self.display_timer.start(16)  # 60fps 更新頻率用於TTS同步
        
    def update_tts_progress(self, current_pos, total_len):
        """優化：更新TTS進度 - 實現真正的實時同步"""
        if not self.tts_sync_enabled:
            return
            
        # 過濾異常進度值
        if current_pos < 0 or current_pos > total_len * 1.5:
            return
            
        # 立即更新進度
        if current_pos >= self.tts_target_position:
            old_position = self.tts_target_position
            self.tts_target_position = current_pos
            self.last_tts_update_time = time.time()
            
            progress_jump = current_pos - old_position
            self._update_tts_sync_display()
            
            # 只在大跳躍時做特殊處理
            if progress_jump > 10:
                self._force_complete_to_position(current_pos)
        
        # 強制發送完成信號
        if current_pos >= total_len and total_len > 0:
            self._check_and_force_completion()
            
    def _check_and_push_sentence_completion(self, current_pos, total_len):
        """ 簡化：輕度檢查句子完成，避免過度推進"""
        if not hasattr(self, 'tc_sentences') or not hasattr(self, 'en_sentences'):
            return
            
        # 計算當前句子進度
        progress_ratio = current_pos / total_len if total_len > 0 else 0
        total_sentences = min(len(self.tc_sentences), len(self.en_sentences))
        target_sentence = int(progress_ratio * total_sentences)
        target_sentence = min(target_sentence, total_sentences - 1)
        
        sentence_progress = (progress_ratio * total_sentences) - target_sentence
        
        #  平衡推進：在合理範圍內推進句子完成
        if sentence_progress >= 0.83 and sentence_progress < 0.88:
            print(f"適度推進句子{target_sentence + 1}完成: {sentence_progress:.3f} → 0.88")
            # 推進到自動完成閾值
            boosted_total_progress = (target_sentence + 0.88) / total_sentences
            boosted_pos = int(boosted_total_progress * total_len)
            self.tts_target_position = boosted_pos
            # 不調用 _update_tts_sync_display()，避免遞迴
            
    def _force_complete_to_position(self, target_pos):
        """強制完成字幕顯示到指定位置 - 解決句子間隔延遲"""
        if not self.is_showing:
            return
            
        print(f"強制完成字幕到位置: {target_pos}")
        
        if self.is_bilingual_mode:
            # 雙語模式強制完成
            if hasattr(self, 'en_text') and self.en_text:
                en_target = min(target_pos, len(self.en_text))
                if en_target > self.en_index:
                    self.en_index = en_target
                    self.en_current_text = self.en_text[:self.en_index]
                    print(f"  英文強制到: {self.en_index}/{len(self.en_text)}")
                    
                    if self.en_index >= len(self.en_text) and not self._en_completed:
                        self._en_completed = True
                        self.en_typing_complete.emit()
            
            if hasattr(self, 'tc_text') and self.tc_text:
                # 中文按比例強制完成
                en_progress = self.en_index / len(self.en_text) if len(self.en_text) > 0 else 0
                tc_target = int(en_progress * len(self.tc_text))
                
                if tc_target > self.tc_index:
                    self.tc_index = tc_target
                    self.tc_current_text = self.tc_text[:self.tc_index]
                    print(f"  中文強制到: {self.tc_index}/{len(self.tc_text)}")
                    
                    if self.tc_index >= len(self.tc_text) and not self._tc_completed:
                        self._tc_completed = True
                        self.tc_typing_complete.emit()
        else:
            # 單語模式強制完成
            if hasattr(self, 'full_text') and self.full_text:
                target_index = min(target_pos, len(self.full_text))
                if target_index > self.current_index:
                    self.current_index = target_index
                    self.current_text = self.full_text[:self.current_index]
                    print(f"  單語強制到: {self.current_index}/{len(self.full_text)}")
                    
                    if self.current_index >= len(self.full_text):
                        if not hasattr(self, '_typing_completed') or not self._typing_completed:
                            self._typing_completed = True
                            self.typing_complete.emit()
        
        # 立即更新顯示
        self.update()
        
    def _update_display(self):
        """統一的顯示更新方法"""
        if not self.is_showing:
            return
        
        # 調試輸出（第一次更新時）
        if not hasattr(self, '_first_update_logged'):
            self._first_update_logged = True
            print(f"📝 字幕開始更新:")
            print(f"   雙語模式: {self.is_bilingual_mode}")
            print(f"   TTS同步: {self.tts_sync_enabled}")
            print(f"   計時器間隔: {self.display_timer.interval()}ms")
        
        # TTS同步模式
        if self.tts_sync_enabled:
            self._update_tts_sync_display()
        else:
            # 常規打字機模式
            self._update_normal()
            
    def _update_normal(self):
        """常規打字機效果更新 - 優化雙語同步"""
        if self.is_bilingual_mode:
            # 是否啟用句子同步模式
            if hasattr(self, 'sentence_sync_mode') and self.sentence_sync_mode:
                # 句子同步模式下，模擬TTS進度
                self._update_sentence_sync_normal()
            else:
                self._update_bilingual_normal()
        else:
            self._update_single_normal()
            
    def _update_single_normal(self):
        """單語常規更新 - 按單詞顯示的打字機效果"""
        if hasattr(self, 'full_text') and self.current_index < len(self.full_text):
            # 按單詞顯示：找到下一個單詞的結束位置
            next_word_end = self._find_next_word_end(self.full_text, self.current_index)
            
            if next_word_end > self.current_index:
                # 顯示到下一個單詞結束
                self.current_index = next_word_end
                self.current_text = self.full_text[:self.current_index]
            else:
                # 如果沒有找到下一個單詞，顯示剩餘的所有文字
                self.current_index = len(self.full_text)
                self.current_text = self.full_text
            
            # 強制重繪
            self.update()
            
            # 偶爾輸出進度（每顯示3個單詞）
            if self._count_words(self.current_text) % 3 == 0:
                progress = self.current_index / len(self.full_text) * 100
                words_shown = self._count_words(self.current_text)
                total_words = self._count_words(self.full_text)
                print(f"   字幕進度: {progress:.0f}% ({words_shown}/{total_words} 單詞)")
        else:
            if not hasattr(self, '_typing_completed') or not self._typing_completed:
                self._typing_completed = True
                self.display_timer.stop()
                print(" 單語字幕顯示完成")
                self.typing_complete.emit()
                
    def _find_next_word_end(self, text, start_index):
        """找到下一個單詞的結束位置"""
        if start_index >= len(text):
            return start_index
            
        # 跳過當前位置的空白字符
        i = start_index
        while i < len(text) and text[i].isspace():
            i += 1
            
        # 找到單詞結束位置（空白字符或標點符號）
        while i < len(text) and not text[i].isspace():
            i += 1
            
        return i
        
    def _count_words(self, text):
        """計算文字中的單詞數量"""
        if not text:
            return 0
        return len(text.split())
            
    def _update_tts_sync_display(self):
        """TTS同步顯示更新 - 簡化和優化"""
        # 計算目標顯示位置
        target_pos = self.tts_target_position
        
        if self.is_bilingual_mode:
            # 🔥 修復：直接使用字符同步模式，實現實時TTS同步
            # 不再使用複雜的句子同步模式
            self._update_character_based_sync(target_pos)
        else:
            # 單語模式 - 直接字符映射
            if hasattr(self, 'full_text') and self.full_text:
                target_index = min(target_pos, len(self.full_text))
                
                if target_index > self.current_index:
                    self.current_index = target_index
                    self.current_text = self.full_text[:self.current_index]
    
                    
                    # 檢查完成
                    if self.current_index >= len(self.full_text):
                        print("📝 單語字幕顯示完成")
                        if not hasattr(self, '_typing_completed') or not self._typing_completed:
                            self._typing_completed = True
                            self.typing_complete.emit()
        
        self.update()
    
    def _update_semantic_sync_display(self, target_pos):
        """ 新增：基於語義分段的同步顯示更新"""
        if not hasattr(self, 'en_text') or not self.en_text:
            return
            
        # 計算英文TTS進度百分比
        en_progress_ratio = target_pos / len(self.en_text) if len(self.en_text) > 0 else 0
        en_progress_ratio = min(en_progress_ratio, 1.0)
        
        # 計算中文的調整進度（使用固定比例，語義同步已移除）
        tc_progress_ratio = en_progress_ratio
        tc_progress_ratio = max(0.0, min(tc_progress_ratio, 1.0))  # 限制在0-1範圍內
        
        # 基於進度計算當前應該顯示的分段
        en_segments_count = len(self.en_semantic_segments)
        tc_segments_count = len(self.tc_semantic_segments)
        
        if en_segments_count > 0 and tc_segments_count > 0:
            # 計算當前英文分段索引
            current_en_segment = min(int(en_progress_ratio * en_segments_count), en_segments_count - 1)
            current_tc_segment = min(int(tc_progress_ratio * tc_segments_count), tc_segments_count - 1)
            
            # 計算分段內部的進度
            en_segment_progress = (en_progress_ratio * en_segments_count) - current_en_segment
            tc_segment_progress = (tc_progress_ratio * tc_segments_count) - current_tc_segment
            
            # 更新英文顯示
            self._update_language_segment_display(
                'en', current_en_segment, en_segment_progress, 
                self.en_semantic_segments, target_pos
            )
            
            # 更新中文顯示（使用調整後的進度）
            tc_target_pos = int(tc_progress_ratio * len(self.tc_text)) if hasattr(self, 'tc_text') else 0
            self._update_language_segment_display(
                'tc', current_tc_segment, tc_segment_progress, 
                self.tc_semantic_segments, tc_target_pos
            )
            
            # 調試信息
            if target_pos % 5 == 0:  # 每5個字符輸出一次調試信息
                print(f" 語義同步 - EN進度:{en_progress_ratio:.3f}({current_en_segment}段), TC進度:{tc_progress_ratio:.3f}({current_tc_segment}段)")
    
    def _update_language_segment_display(self, lang, segment_index, segment_progress, segments, target_char_pos):
        """更新特定語言的分段顯示"""
        if segment_index >= len(segments):
            return
            
        # 計算應該顯示到哪個字符
        total_displayed_chars = 0
        
        # 顯示完整的前面分段
        for i in range(segment_index):
            total_displayed_chars += len(segments[i])
        
        # 顯示當前分段的部分內容
        current_segment = segments[segment_index]
        chars_in_current_segment = int(segment_progress * len(current_segment))
        total_displayed_chars += chars_in_current_segment
        
        # 確保不超過目標位置
        total_displayed_chars = min(total_displayed_chars, target_char_pos)
        
        # 更新對應語言的顯示
        if lang == 'en':
            if total_displayed_chars > self.en_index:
                self.en_index = total_displayed_chars
                self.en_current_text = self.en_text[:self.en_index] if hasattr(self, 'en_text') else ""
                
                # 檢查英文完成
                if self.en_index >= len(self.en_text) and not self._en_completed:
                    self._en_completed = True
                    self.en_typing_complete.emit()
                    
        elif lang == 'tc':
            if total_displayed_chars > self.tc_index:
                self.tc_index = total_displayed_chars
                self.tc_current_text = self.tc_text[:self.tc_index] if hasattr(self, 'tc_text') else ""
                
                # 檢查中文完成
                if self.tc_index >= len(self.tc_text) and not self._tc_completed:
                    self._tc_completed = True
                    self.tc_typing_complete.emit()
    
    def _update_character_based_sync(self, target_pos):
        # 雙語模式
        if hasattr(self, 'en_text') and self.en_text:
            en_target = min(target_pos, len(self.en_text))
            
            if en_target > self.en_index:
                self.en_index = en_target
                self.en_current_text = self.en_text[:self.en_index]
                
                # 檢查英文完成
                if self.en_index >= len(self.en_text) and not self._en_completed:
                    self._en_completed = True
                    self.en_typing_complete.emit()

            if hasattr(self, 'tc_text') and self.tc_text:
                en_progress = self.en_index / len(self.en_text) if len(self.en_text) > 0 else 0
                tc_target = int(en_progress * len(self.tc_text))
                
                if tc_target > self.tc_index:
                    self.tc_index = tc_target
                    self.tc_current_text = self.tc_text[:self.tc_index]
                    
                    # 檢查中文完成
                    if self.tc_index >= len(self.tc_text) and not self._tc_completed:
                        self._tc_completed = True
                        self.tc_typing_complete.emit()
        
    def _update_normal_display(self):
        """常規顯示更新（非TTS同步）- 優化雙語同步"""
        if self.is_bilingual_mode:
            if hasattr(self, 'sentence_sync_mode') and self.sentence_sync_mode:
                # 句子同步模式下，模擬TTS進度
                self._update_sentence_sync_normal()
            else:
                self._update_bilingual_normal()
        else:
            self._update_single_normal()
            
    def _update_bilingual_normal(self):
        """雙語常規更新 - 按單詞顯示，英文比中文快"""
        # 計算英文進度
        en_completed = (hasattr(self, 'en_text') and hasattr(self, 'en_index') 
                       and self.en_index >= len(self.en_text))
        tc_completed = (hasattr(self, 'tc_text') and hasattr(self, 'tc_index') 
                       and self.tc_index >= len(self.tc_text))
        
        if en_completed and tc_completed:
            # 雙語都完成
            if not self._typing_completed:
                self._typing_completed = True
                print("📝 雙語字幕打字完成")
                self.typing_complete.emit()
            return
        
        # 英文按單詞推進 - 英文會比中文快
        if hasattr(self, 'en_text') and self.en_text and not self._en_completed:
            if self.en_index < len(self.en_text):
                # 找到下一個英文單詞的結束位置
                next_word_end = self._find_next_word_end(self.en_text, self.en_index)
                
                if next_word_end > self.en_index:
                    self.en_index = next_word_end
                    self.en_current_text = self.en_text[:self.en_index]
                else:
                    # 顯示剩餘的所有英文
                    self.en_index = len(self.en_text)
                    self.en_current_text = self.en_text
                
                if self.en_index >= len(self.en_text):
                    self._en_completed = True
                    self.en_typing_complete.emit()
        
        # 中文同步推進 - 根據英文進度調整
        if hasattr(self, 'tc_text') and self.tc_text and not self._tc_completed:
            if self.tc_index < len(self.tc_text):
                # 計算中文的同步位置
                if hasattr(self, 'en_text') and len(self.en_text) > 0:
                    en_progress = self.en_index / len(self.en_text)
                    
                    # 中文稍微滯後，讓英文先顯示
                    adjusted_progress = min(en_progress * 0.8, 1.0)  # 中文進度是英文的80%
                    target_tc_index = int(adjusted_progress * len(self.tc_text))
                    
                    # 確保中文能跟上英文進度
                    if target_tc_index > self.tc_index:
                        # 中文按字符推進，但速度較慢
                        self.tc_index += 1
                        self.tc_current_text = self.tc_text[:self.tc_index]
                    elif self._en_completed and self.tc_index < len(self.tc_text):
                        # 如果英文已完成但中文還沒完成，繼續推進中文
                        self.tc_index += 1
                        self.tc_current_text = self.tc_text[:self.tc_index]
                else:
                    # 如果沒有英文參考，正常推進
                    self.tc_index += 1
                    self.tc_current_text = self.tc_text[:self.tc_index]
                
                if self.tc_index >= len(self.tc_text):
                    self._tc_completed = True
                    self.tc_typing_complete.emit()
        
        # 強制重繪
        self.update()
        
        #  偶爾輸出進度（每顯示2個英文單詞）
        if hasattr(self, 'en_index') and self._count_words(self.en_current_text) % 2 == 0:
            en_words = self._count_words(self.en_current_text)
            total_en_words = self._count_words(self.en_text) if self.en_text else 0
            tc_chars = len(self.tc_current_text)
            total_tc_chars = len(self.tc_text) if self.tc_text else 0
            print(f"   雙語進度: EN {en_words}/{total_en_words} 單詞, TC {tc_chars}/{total_tc_chars} 字符")
        
        # 檢查整體完成狀態
        if self._en_completed and self._tc_completed and not self._typing_completed:
            self._typing_completed = True
            print("📝 雙語字幕全部顯示完成")
            self.typing_complete.emit()
            

            
    def disable_tts_sync(self):
        """禁用TTS同步並完成顯示"""
        if not self.tts_sync_enabled:
            return
            
        print("TTS完成，完成字幕顯示")
        self.tts_sync_enabled = False
        self._typing_completed = False  # 重置標誌供下次使用
        
        # 停止計時器
        if self.display_timer.isActive():
            self.display_timer.stop()
        
        # 完成所有字幕顯示
        if self.is_bilingual_mode:
            if hasattr(self, 'tc_text') and hasattr(self, 'en_text'):
                self.tc_current_text = self.tc_text
                self.en_current_text = self.en_text
                self.tc_index = len(self.tc_text)
                self.en_index = len(self.en_text)
                
                if not self._tc_completed:
                    self._tc_completed = True
                    self.tc_typing_complete.emit()
                    
                if not self._en_completed:
                    self._en_completed = True
                    self.en_typing_complete.emit()
                    
                self.typing_complete.emit()
        else:
            if hasattr(self, 'full_text'):
                self.current_text = self.full_text
                self.current_index = len(self.full_text)
                self.typing_complete.emit()
        
        self.update()
            
    def hide(self):
        """隱藏字幕"""
        if self.display_timer.isActive():
            self.display_timer.stop()
        
        self.current_text = ""
        self.is_showing = False
        self.is_bilingual_mode = False
        
        # 重置狀態
        self.tc_current_text = ""
        self.en_current_text = ""
        self._tc_completed = False
        self._en_completed = False
        
        # 重置TTS同步
        self.tts_sync_enabled = False
        
        super().hide()
        
    def paintEvent(self, event):
        """繪製字幕和背景"""
        if not self.is_showing:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setFont(self.caption_font)
        metrics = QFontMetrics(self.caption_font)
        
        if self.is_bilingual_mode:
            self._paint_bilingual(painter, metrics)
        else:
            self._paint_single_language(painter, metrics)
                
    def _paint_single_language(self, painter, metrics):
        """繪製單語字幕 - 帶逐行背景"""
        if not self.current_text:
            return
            
        # 獲取完整文字的所有行
        full_lines = self._wrap_text(self.full_text, metrics) if self.full_text else []
        if not full_lines:
            return
            
        # 根據當前顯示的字符數量，計算應該顯示到第幾行
        current_lines, current_line_partial = self._get_current_display_lines(self.current_text, full_lines)
        
        line_height = metrics.height()
        total_height = len(full_lines) * (line_height + self.line_spacing) - self.line_spacing + 2 * self.padding
        
        # 確保文字在可見區域內
        available_height = self.height()
        if total_height > available_height:
            y_offset = 0
        else:
            # 使用 target_position_ratio 計算字幕位置
            y_offset = int(available_height * self.target_position_ratio) - total_height
        
        y_offset = max(0, y_offset)
        
        # 繪製背景和文字 - 只繪製已顯示的行
        for i in range(len(current_lines)):
            line_text = current_lines[i]
            if i == len(current_lines) - 1 and current_line_partial:
                # 最後一行可能只顯示部分文字
                line_text = current_line_partial
            
            if line_text.strip():
                self._draw_text_line_with_background(painter, line_text, i, y_offset, line_height, metrics)
                
    def _paint_bilingual(self, painter, metrics):
        """繪製雙語字幕 - 帶逐行背景"""
        line_height = metrics.height()
        
        # 獲取完整文字的所有行
        tc_full_lines = self._wrap_text(self.tc_text, metrics) if hasattr(self, 'tc_text') and self.tc_text else []
        en_full_lines = self._wrap_text(self.en_text, metrics) if hasattr(self, 'en_text') and self.en_text else []
        
        # 計算當前顯示的行
        tc_current_lines, tc_partial = [], ""
        en_current_lines, en_partial = [], ""
        
        if hasattr(self, 'tc_current_text') and self.tc_current_text:
            tc_current_lines, tc_partial = self._get_current_display_lines(self.tc_current_text, tc_full_lines)
        
        if hasattr(self, 'en_current_text') and self.en_current_text:
            en_current_lines, en_partial = self._get_current_display_lines(self.en_current_text, en_full_lines)
        
        # 計算總行數（包括已顯示的）
        total_displayed_lines = len(tc_current_lines) + len(en_current_lines)
        if tc_partial:
            total_displayed_lines += 1
        if en_partial:
            total_displayed_lines += 1
        if len(tc_current_lines) > 0 and len(en_current_lines) > 0:
            total_displayed_lines += 1  # 語言間隔
            
        if total_displayed_lines == 0:
            return  # 沒有文字要顯示
            
        # 計算完整佈局（基於所有文字）
        total_full_lines = len(tc_full_lines) + len(en_full_lines)
        if total_full_lines > 0 and len(tc_full_lines) > 0 and len(en_full_lines) > 0:
            total_full_lines += 1  # 語言間隔
            
        total_height = total_full_lines * (line_height + self.line_spacing) - self.line_spacing + 2 * self.padding
        
        # 確保文字在可見區域內
        available_height = self.height()
        if total_height > available_height:
            y_offset = 0
        else:
            # 使用 target_position_ratio 計算字幕位置
            y_offset = int(available_height * self.target_position_ratio) - total_height
        
        y_offset = max(0, y_offset)
        
        current_line = 0
        
        # 繪製中文（已顯示的行）
        for i, line in enumerate(tc_current_lines):
            if line.strip():
                self._draw_text_line_with_background(painter, line, current_line, y_offset, line_height, metrics)
            current_line += 1
            
        # 繪製中文部分行
        if tc_partial and tc_partial.strip():
            self._draw_text_line_with_background(painter, tc_partial, current_line, y_offset, line_height, metrics)
            current_line += 1
            
        # 語言之間的間隔
        if len(tc_current_lines) > 0 and len(en_current_lines) > 0:
            current_line += 1
            
        # 繪製英文（已顯示的行）
        for i, line in enumerate(en_current_lines):
            if line.strip():
                self._draw_text_line_with_background(painter, line, current_line, y_offset, line_height, metrics)
            current_line += 1
            
        # 繪製英文部分行
        if en_partial and en_partial.strip():
            self._draw_text_line_with_background(painter, en_partial, current_line, y_offset, line_height, metrics)
            current_line += 1
                
    def _wrap_text(self, text, metrics):
        """基於字符數量的統一換行處理 - 中英文使用相同限制"""
        if not text:
            return []
            
        lines = []
        current_line = ""
        current_weight = 0.0
        
        # 處理每個字符
        i = 0
        while i < len(text):
            char = text[i]
            
            # 計算字符權重
            char_weight = self._get_char_weight(char)
            
            # 檢查是否超過限制
            if current_weight + char_weight <= self.max_chars_per_line:
                # 字符可以添加到當前行
                current_line += char
                current_weight += char_weight
                i += 1
            else:
                # 當前行已滿，需要換行
                if current_line:
                    # 嘗試在合適的地方斷行
                    wrapped_result = self._smart_break_line_by_chars(current_line, char, text, i)
                    lines.append(wrapped_result['line'])
                    current_line = wrapped_result['remaining']
                    current_weight = self._calculate_line_weight(current_line)
                    i = wrapped_result['next_index']
                else:
                    # 單個字符就超限了，強制添加
                    current_line = char
                    current_weight = char_weight
                    i += 1
        
        # 添加最後一行
        if current_line:
            lines.append(current_line)
            
        return lines if lines else [""]
        
    def _get_char_weight(self, char):
        """計算字符權重 - 改進版本，更平衡中英文"""
        # 中文字符（包括中文標點）
        if '\u4e00' <= char <= '\u9fff' or char in '，。！？；：「」『』':
            return self.chinese_char_weight
        # 英文字母和數字
        elif char.isalnum():
            return 1.0
        # 英文標點符號
        elif char in ',.!?;:':
            return 0.8  # 標點符號權重稍低
        # 空格
        elif char.isspace():
            return 0.5  # 空格權重更低
        # 其他字符
        else:
            return 1.0
            
    def _calculate_line_weight(self, line):
        """計算一行文字的總權重"""
        total_weight = 0.0
        for char in line:
            total_weight += self._get_char_weight(char)
        return total_weight
        
    def _smart_break_line_by_chars(self, current_line, next_char, full_text, current_index):
        """基於字符數量的智能斷行 - 改進版本，更適合中英文混合"""
        # 優先斷點順序：標點符號 > 空格 > 中英文邊界 > 強制斷行
        
        # 1. 在標點符號後斷行（中英文）
        punctuation = ",，。！？；：.!?;:"
        
        # 從行尾往前找合適的斷點（最多回溯15個字符）
        for i in range(len(current_line) - 1, max(0, len(current_line) - 15), -1):
            if current_line[i] in punctuation:
                # 在標點後斷行
                break_point = i + 1
                return {
                    'line': current_line[:break_point],
                    'remaining': current_line[break_point:] + next_char,
                    'next_index': current_index + 1
                }
        
        # 2. 在空格處斷行（主要為英文）
        for i in range(len(current_line) - 1, max(0, len(current_line) - 12), -1):
            if current_line[i] == ' ':
                break_point = i + 1
                return {
                    'line': current_line[:break_point].rstrip(),
                    'remaining': current_line[break_point:].lstrip() + next_char,
                    'next_index': current_index + 1
                }
        
        # 3. 在中英文邊界處斷行（新增）
        for i in range(len(current_line) - 1, max(0, len(current_line) - 10), -1):
            if self._is_language_boundary(current_line[i], current_line[i+1] if i+1 < len(current_line) else ''):
                break_point = i + 1
                return {
                    'line': current_line[:break_point],
                    'remaining': current_line[break_point:] + next_char,
                    'next_index': current_index + 1
                }
        
        # 4. 如果找不到好的斷點，在2/3處強制斷行（改進）
        break_point = max(1, len(current_line) * 2 // 3)
        return {
            'line': current_line[:break_point],
            'remaining': current_line[break_point:] + next_char,
            'next_index': current_index + 1
        }
        
    def _is_language_boundary(self, char1, char2):
        """檢查是否為中英文邊界"""
        def is_chinese(char):
            return '\u4e00' <= char <= '\u9fff' or char in '，。！？；：「」『』'
        
        def is_english(char):
            return char.isascii() and char.isalnum()
        
        # 中英文邊界：中文後面跟英文，或英文後面跟中文
        return (is_chinese(char1) and is_english(char2)) or (is_english(char1) and is_chinese(char2))
        
    def _smart_break_line(self, current_line, next_char, full_text, current_index):
        """智能斷行 - 優先在合適位置斷開（舊版本，保留兼容性）"""
        # 重定向到新的字符數量版本
        return self._smart_break_line_by_chars(current_line, next_char, full_text, current_index)
        
    def _get_current_display_lines(self, current_text, full_lines):
        """根據當前顯示的字符計算應該顯示到第幾行"""
        if not current_text or not full_lines:
            return [], ""
            
        char_count = 0
        current_lines = []
        current_line_partial = ""
        
        for line in full_lines:
            if char_count + len(line) <= len(current_text):
                # 這行完全顯示
                current_lines.append(line)
                char_count += len(line)
            else:
                # 這行部分顯示
                remaining_chars = len(current_text) - char_count
                if remaining_chars > 0:
                    current_line_partial = line[:remaining_chars]
                break
                
        return current_lines, current_line_partial
        
    def _draw_text_line_with_background(self, painter, text, line_index, y_offset, line_height, metrics):
        """繪製帶背景的單行文字"""
        # 計算位置
        y = y_offset + self.padding + line_index * (line_height + self.line_spacing)
        
        # 計算文字寬度並居中
        text_width = metrics.horizontalAdvance(text)
        x = (self.width() - text_width) // 2
        
        # 繪製半透明黑色背景
        background_padding = 8
        background_rect = QRect(
            x - background_padding, 
            y, 
            text_width + 2 * background_padding, 
            line_height
        )
        
        painter.fillRect(background_rect, QColor(0, 0, 0, 102))  # 40% 透明度 (255 * 0.4 = 102)
        
        # 繪製文字陰影
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(x + 2, y + line_height - 2, text)
        
        # 繪製主文字
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(x, y + line_height - 4, text)
        
    def _draw_text_line(self, painter, text, line_index, y_offset, line_height, metrics):
        """繪製單行文字（無背景版本）"""
        # 重定向到帶背景版本
        self._draw_text_line_with_background(painter, text, line_index, y_offset, line_height, metrics)

    def _create_semantic_segments(self, tc_text, en_text):
        """創建語義分段 - 智能分析中英文的自然斷點"""
        print("🎯 開始創建語義分段...")
        
        # 分析中文分段點（基於標點符號）
        tc_breaks = self._find_semantic_breaks(tc_text, is_chinese=True)
        en_breaks = self._find_semantic_breaks(en_text, is_chinese=False)
        
        # 創建分段
        self.tc_semantic_segments = self._create_segments_from_breaks(tc_text, tc_breaks)
        self.en_semantic_segments = self._create_segments_from_breaks(en_text, en_breaks)
        
        # 平衡分段數量（確保兩種語言有相同的分段數）
        self._balance_segments()
        
        print(f"  中文分段數: {len(self.tc_semantic_segments)}")
        print(f"  英文分段數: {len(self.en_semantic_segments)}")
        for i, (tc_seg, en_seg) in enumerate(zip(self.tc_semantic_segments, self.en_semantic_segments)):
            print(f"  分段 {i}: TC='{tc_seg[:20]}...' EN='{en_seg[:20]}...'")
    
    def _find_semantic_breaks(self, text, is_chinese=True):
        """找到語義分段點"""
        breaks = [0]  # 開始位置
        
        if is_chinese:
            # 中文斷點：主要標點符號
            break_chars = '。！？；：，'
            for i, char in enumerate(text):
                if char in break_chars:
                    # 在標點符號後添加斷點
                    next_pos = i + 1
                    if next_pos < len(text) and next_pos not in breaks:
                        breaks.append(next_pos)
        else:
            # 英文斷點：句號、問號、感嘆號、分號
            break_chars = '.!?;'
            for i, char in enumerate(text):
                if char in break_chars:
                    # 在標點符號後添加斷點，跳過空格
                    next_pos = i + 1
                    while next_pos < len(text) and text[next_pos] == ' ':
                        next_pos += 1
                    if next_pos < len(text) and next_pos not in breaks:
                        breaks.append(next_pos)
        
        # 確保結尾位置
        if len(text) not in breaks:
            breaks.append(len(text))
        
        return sorted(breaks)
    
    def _create_segments_from_breaks(self, text, breaks):
        """從斷點創建分段"""
        segments = []
        for i in range(len(breaks) - 1):
            start = breaks[i]
            end = breaks[i + 1]
            segment = text[start:end].strip()
            if segment:  # 只添加非空分段
                segments.append(segment)
        return segments
    
    def _balance_segments(self):
        """平衡中英文分段數量"""
        tc_count = len(self.tc_semantic_segments)
        en_count = len(self.en_semantic_segments)
        
        if tc_count == en_count:
            return  # 已經平衡
        
        # 選擇較少分段的語言進行合併
        if tc_count > en_count:
            # 合併中文分段
            self._merge_segments(self.tc_semantic_segments, en_count)
        else:
            # 合併英文分段
            self._merge_segments(self.en_semantic_segments, tc_count)
        
        print(f"分段平衡後: 中文={len(self.tc_semantic_segments)}, 英文={len(self.en_semantic_segments)}")
    
    def _merge_segments(self, segments, target_count):
        """合併分段到目標數量"""
        while len(segments) > target_count:
            # 找到最短的相鄰分段對並合併
            min_length = float('inf')
            merge_index = 0
            
            for i in range(len(segments) - 1):
                combined_length = len(segments[i]) + len(segments[i + 1])
                if combined_length < min_length:
                    min_length = combined_length
                    merge_index = i
            
            # 合併分段
            segments[merge_index] = segments[merge_index] + " " + segments[merge_index + 1]
            segments.pop(merge_index + 1)

    def set_bilingual_text_sentence_sync(self, tc_text, en_text, typing_speed=80):
        """設定句子同步雙語文字 - 簡單有效的同步方案"""
        if not tc_text or not en_text:
            return False
            
        print(f"🎯 啟用句子同步模式，打字速度: {typing_speed}ms/字")
        
        #  儲存打字速度設置
        self.typing_speed = typing_speed
        print(f"🔧 句子同步設置: typing_speed = {typing_speed}ms")
        
        # 啟用雙語模式
        self.is_bilingual_mode = True
        self.sentence_sync_mode = True  # 啟用句子同步模式
        
        # 按句子分割
        self.tc_sentences = self._split_into_sentences(tc_text, is_chinese=True)
        self.en_sentences = self._split_into_sentences(en_text, is_chinese=False)
        
        # 儲存完整文字
        self.tc_text = tc_text
        self.en_text = en_text
        
        # 重置狀態
        self.tc_current_text = ""
        self.en_current_text = ""
        self.current_sentence_index = 0
        self.tc_index = 0
        self.en_index = 0
        self._tc_completed = False
        self._en_completed = False
        self._typing_completed = False
        self.is_showing = True
        
        print(f"📝 句子分割結果:")
        print(f"  中文: {len(self.tc_sentences)}句")
        print(f"  英文: {len(self.en_sentences)}句")
        
        # 顯示對應句子
        max_sentences = min(len(self.tc_sentences), len(self.en_sentences), 3)  # 最多顯示3句
        for i in range(max_sentences):
            print(f"  句子{i+1}: [{self.tc_sentences[i]}] | [{self.en_sentences[i]}]")
        
        # 🎯 重要：啟動顯示機制
        self.show()
        
        # 啟動顯示計時器 -  根據typing_speed設置間隔
        if not self.tts_sync_enabled:
            #  修復：允許更快的打字速度，降低最小間隔限制
            timer_interval = max(self.typing_speed, 5)  # 最小5ms間隔，允許配置的3ms生效
            self.display_timer.start(timer_interval)
            print(f"句子同步：使用普通顯示計時器，間隔{timer_interval}ms (typing_speed: {self.typing_speed}ms)")
        else:
            # TTS同步模式，使用快速更新（保持TTS同步精確性）
            self.display_timer.start(16)  # 60fps
            print(f"句子同步：TTS模式，使用60fps更新頻率")
        
        self.update()
        print(" 句子同步顯示機制已啟動")
        
        return True
        
    def configure_auto_completion(self, auto_complete_threshold=0.88, acceleration_threshold=0.80, 
                                acceleration_multiplier=1.6, push_completion_threshold=0.85):
        """ 新增：配置自動完成和加速參數"""
        self.auto_complete_threshold = auto_complete_threshold
        self.acceleration_threshold = acceleration_threshold
        self.acceleration_multiplier = acceleration_multiplier
        self.push_completion_threshold = push_completion_threshold
        
        print(f"🔧 自動完成設定已更新:")
        print(f"   自動完成閾值: {auto_complete_threshold*100:.0f}%")
        print(f"   開始加速閾值: {acceleration_threshold*100:.0f}%")
        print(f"   加速倍數: {acceleration_multiplier}×")
        print(f"   強制推進閾值: {push_completion_threshold*100:.0f}%")
        
    def _split_into_sentences(self, text, is_chinese=True):
        """將文字分割成句子"""
        if is_chinese:
            # 中文按句號、問號、驚嘆號分割
            sentences = re.split(r'[。！？]', text)
        else:
            # 英文按句號、問號、驚嘆號分割
            sentences = re.split(r'[.!?]', text)
            
        # 清理並過濾空句子
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
        
    def _update_sentence_sync_display(self, target_pos):
        """更新句子同步顯示 -  新增94%自動完成防止卡頓"""
        if not hasattr(self, 'tc_sentences') or not hasattr(self, 'en_sentences'):
            return
            
        if not self.tc_sentences or not self.en_sentences:
            return
            
        # 計算英文TTS進度 - 移除過度保守的限制
        en_progress_ratio = target_pos / len(self.en_text) if len(self.en_text) > 0 else 0
        en_progress_ratio = min(en_progress_ratio, 1.0)
        
        # 🎯 關鍵修復：移除進度限制，讓字幕直接跟隨TTS進度
        # 不再限制字幕進度，讓字幕能夠跟上TTS的實際速度
        
        
        # 🎯 修復句子切換邏輯 - 更響應TTS進度
        total_sentences = min(len(self.tc_sentences), len(self.en_sentences))
        
        # 直接使用TTS進度計算句子進度，不做過度保守的限制
        raw_sentence_progress = en_progress_ratio * total_sentences
        current_sentence_idx = int(raw_sentence_progress)
        sentence_progress_in_current = raw_sentence_progress - current_sentence_idx
        
        if sentence_progress_in_current >= 0.75 and current_sentence_idx < total_sentences - 1:  # 降低到75%
            target_sentence = current_sentence_idx + 1
            sentence_progress = 0.0  # 新句子從0開始
            
        else:
            target_sentence = current_sentence_idx
            sentence_progress = sentence_progress_in_current
        
        target_sentence = min(target_sentence, total_sentences - 1)
        sentence_progress = min(sentence_progress, 1.0)

        original_progress = sentence_progress
        if sentence_progress >= 0.70:  # 降低到70%就自動完成
            sentence_progress = 1.0  # 強制完成當前句子
            
        
        # 更新顯示內容
        if target_sentence != self.current_sentence_index:
            self.current_sentence_index = target_sentence
            print(f" 切換到句子 {target_sentence + 1}: [{self.tc_sentences[target_sentence]}] | [{self.en_sentences[target_sentence]}]")
        
        #  簡化邏輯：正常顯示已完成的句子
        completed_tc_sentences = self.tc_sentences[:target_sentence] if target_sentence > 0 else []
        completed_en_sentences = self.en_sentences[:target_sentence] if target_sentence > 0 else []
        
        # 當前句子的部分顯示
        if target_sentence < len(self.tc_sentences) and target_sentence < len(self.en_sentences):
            current_tc_sentence = self.tc_sentences[target_sentence]
            current_en_sentence = self.en_sentences[target_sentence]
            

            if sentence_progress >= 1.0:
                # 完整顯示當前句子
                partial_tc = current_tc_sentence
                partial_en = current_en_sentence
            else:
                # 🚀 更積極的加速模式：從50%開始加速
                if sentence_progress >= 0.50:  # 降低加速閾值
                    # 使用更強的加速係數，確保字幕跟上TTS
                    acceleration_factor = 1.8  # 增加加速係數
                    accelerated_progress = 0.50 + (sentence_progress - 0.50) * acceleration_factor
                    accelerated_progress = min(accelerated_progress, 1.0)  # 允許完全完成
                    tc_chars = int(len(current_tc_sentence) * accelerated_progress)
                    en_chars = int(len(current_en_sentence) * accelerated_progress)
    
                else:
                    # 正常進度顯示
                    tc_chars = int(len(current_tc_sentence) * sentence_progress)
                    en_chars = int(len(current_en_sentence) * sentence_progress)
                
                partial_tc = current_tc_sentence[:tc_chars]
                partial_en = current_en_sentence[:en_chars]
            
            #  改進組合顯示文字：嚴格防止跨句顯示
            # 中文組合
            if completed_tc_sentences:
                self.tc_current_text = '。'.join(completed_tc_sentences)
                if partial_tc:
                    self.tc_current_text += '。' + partial_tc
            else:
                self.tc_current_text = partial_tc if partial_tc else ""
                
            # 英文組合
            if completed_en_sentences:
                self.en_current_text = '. '.join(completed_en_sentences)
                if partial_en:
                    self.en_current_text += '. ' + partial_en
            else:
                self.en_current_text = partial_en if partial_en else ""
                
            #  移除過度嚴格的安全檢查，讓句子正常完成
        
        #  修復：直接更新顯示，避免遞迴調用
        self.update()
        
        # 移除過度頻繁的進度調試輸出

    def _update_sentence_sync_normal(self):
        """句子同步模式的常規顯示更新（非TTS）"""
        if not hasattr(self, 'tc_sentences') or not hasattr(self, 'en_sentences'):
            return
            
        if not self.tc_sentences or not self.en_sentences:
            return
            
        # 計算進度（基於時間或字符數）
        total_sentences = min(len(self.tc_sentences), len(self.en_sentences))
        
        # 基於英文當前顯示位置模擬句子進度 -  根據typing_speed調整
        if hasattr(self, 'en_text') and self.en_text:
            # 模擬TTS進度，基於字符數逐步增加
            if self.en_index < len(self.en_text):
                #  修復：正確根據typing_speed計算字符增加速度
                # typing_speed越小（毫秒），字符增加越快，但不是直接反比例
                # 使用更合理的計算方式
                if self.typing_speed <= 10:
                    chars_per_update = 3  # 很快，每次3個字符
                elif self.typing_speed <= 30:
                    chars_per_update = 2  # 中等快，每次2個字符
                elif self.typing_speed <= 60:
                    chars_per_update = 1  # 正常，每次1個字符
                else:
                    chars_per_update = 1  # 慢速，每次1個字符
                    
                self.en_index = min(self.en_index + chars_per_update, len(self.en_text))
                # 移除重複的字符增加調試輸出
                
            progress_ratio = self.en_index / len(self.en_text)
            target_sentence = int(progress_ratio * total_sentences)
            target_sentence = min(target_sentence, total_sentences - 1)
            
            # 計算當前句子內的進度
            sentence_progress = (progress_ratio * total_sentences) - target_sentence
            sentence_progress = min(sentence_progress, 1.0)
            
            #  同樣添加自動完成邏輯到非TTS模式
            if sentence_progress >= self.auto_complete_threshold:
                sentence_progress = 1.0  # 強制完成當前句子
                # 移除重複的非TTS自動完成調試輸出
            
            # 更新顯示內容
            if target_sentence != self.current_sentence_index:
                self.current_sentence_index = target_sentence
                print(f" 切換到句子 {target_sentence + 1}: [{self.tc_sentences[target_sentence]}] | [{self.en_sentences[target_sentence]}]")
            
            # 顯示完整的前面句子 + 當前句子的部分內容
            completed_tc_sentences = self.tc_sentences[:target_sentence]
            completed_en_sentences = self.en_sentences[:target_sentence]
            
            # 當前句子的部分顯示
            if target_sentence < len(self.tc_sentences) and target_sentence < len(self.en_sentences):
                current_tc_sentence = self.tc_sentences[target_sentence]
                current_en_sentence = self.en_sentences[target_sentence]
                
                #  智能字符進度計算 - 與TTS模式保持一致
                if sentence_progress >= 1.0:
                    # 完整顯示當前句子
                    partial_tc = current_tc_sentence
                    partial_en = current_en_sentence
                else:
                    #  溫和加速模式：避免過度超前（非TTS）
                    if sentence_progress >= self.acceleration_threshold:
                        # 加速閾值到自動完成閾值之間使用溫和加速進度
                        accelerated_progress = self.acceleration_threshold + (sentence_progress - self.acceleration_threshold) * self.acceleration_multiplier
                        accelerated_progress = min(accelerated_progress, 0.92)  # 限制不超過92%，避免過度超前
                        tc_chars = int(len(current_tc_sentence) * accelerated_progress)
                        en_chars = int(len(current_en_sentence) * accelerated_progress)
                        # 移除重複的非TTS加速調試輸出
                    else:
                        # 正常進度顯示
                        tc_chars = int(len(current_tc_sentence) * sentence_progress)
                        en_chars = int(len(current_en_sentence) * sentence_progress)
                    
                    partial_tc = current_tc_sentence[:tc_chars]
                    partial_en = current_en_sentence[:en_chars]
                
                # 組合顯示文字
                self.tc_current_text = '。'.join(completed_tc_sentences)
                if self.tc_current_text and partial_tc:
                    self.tc_current_text += '。' + partial_tc
                elif partial_tc:
                    self.tc_current_text = partial_tc
                    
                self.en_current_text = '. '.join(completed_en_sentences)
                if self.en_current_text and partial_en:
                    self.en_current_text += '. ' + partial_en
                elif partial_en:
                    self.en_current_text = partial_en
                
                # 更新索引以匹配當前顯示
                self.tc_index = len(self.tc_current_text)
        
        # 檢查是否完成
        if self.en_index >= len(self.en_text):
            if not self._en_completed:
                self._en_completed = True
                self.en_typing_complete.emit()
                
        if self.tc_index >= len(self.tc_text):
            if not self._tc_completed:
                self._tc_completed = True
                self.tc_typing_complete.emit()
                
        # 檢查整體完成
        if self._tc_completed and self._en_completed:
            self.display_timer.stop()
            self.typing_complete.emit()
            
        self.update()

    def _check_and_force_completion(self):
        """檢查並強制完成字幕顯示"""
        if not self.tts_sync_enabled:
            return
            
        print(f"🔍 檢查字幕完成狀態:")
        
        if self.is_bilingual_mode:
            # 雙語模式檢查
            en_completed = (hasattr(self, 'en_text') and hasattr(self, 'en_index') 
                           and self.en_index >= len(self.en_text))
            tc_completed = (hasattr(self, 'tc_text') and hasattr(self, 'tc_index') 
                           and self.tc_index >= len(self.tc_text))
            
            print(f"   英文完成: {en_completed} ({self.en_index}/{len(self.en_text) if hasattr(self, 'en_text') else 0})")
            print(f"   中文完成: {tc_completed} ({self.tc_index}/{len(self.tc_text) if hasattr(self, 'tc_text') else 0})")
            
            # 強制完成未完成的語言
            if not en_completed and hasattr(self, 'en_text'):
                print(f"   🔧 強制完成英文字幕")
                self.en_index = len(self.en_text)
                self.en_current_text = self.en_text
                if not self._en_completed:
                    self._en_completed = True
                    self.en_typing_complete.emit()
                    
            if not tc_completed and hasattr(self, 'tc_text'):
                print(f"   🔧 強制完成中文字幕")
                self.tc_index = len(self.tc_text)
                self.tc_current_text = self.tc_text
                if not self._tc_completed:
                    self._tc_completed = True
                    self.tc_typing_complete.emit()
            
            # 檢查整體完成
            if en_completed and tc_completed and not self._typing_completed:
                print(f"    雙語字幕全部完成，發送完成信號")
                self._typing_completed = True
                self.typing_complete.emit()
        else:
            # 單語模式檢查
            single_completed = (hasattr(self, 'full_text') and hasattr(self, 'current_index') 
                               and self.current_index >= len(self.full_text))
            
            print(f"   單語完成: {single_completed} ({self.current_index}/{len(self.full_text) if hasattr(self, 'full_text') else 0})")
            
            if not single_completed and hasattr(self, 'full_text'):
                print(f"   🔧 強制完成單語字幕")
                self.current_index = len(self.full_text)
                self.current_text = self.full_text
                if not hasattr(self, '_typing_completed') or not self._typing_completed:
                    self._typing_completed = True
                    self.typing_complete.emit()
        
        self.update()