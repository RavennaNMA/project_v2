# Location: project_v2/services/tts_service.py
# Usage: TTS 語音合成服務，使用 Kokoro TTS 引擎進行高品質語音合成

import threading
import queue
import time
import re
import io
import soundfile as sf
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from utils import TTSConfigLoader

# 導入語音修改服務
try:
    from .voice_mod_service import VoiceModService
    from utils.voice_mod_config_loader import VoiceModConfigLoader
    VOICE_MOD_AVAILABLE = True
except ImportError:
    VOICE_MOD_AVAILABLE = False
    print("警告: 語音修改服務不可用，將跳過語音效果處理")

try:
    from kokoro import KPipeline
    import torch
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False
    print("Kokoro TTS 不可用，請安裝: pip install kokoro>=0.9.4 soundfile torch")

# 播放音訊的跨平台實作
try:
    import pygame
    pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=256)  # 減少緩衝延遲
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("警告: pygame 不可用，將無法播放音訊")


class KokoroTTSWorker(QThread):
    """Kokoro TTS 工作線程，處理語音合成"""
    
    tts_started = pyqtSignal()
    tts_finished = pyqtSignal()
    tts_error = pyqtSignal(str)
    tts_progress = pyqtSignal(int, int)  # (當前字符位置, 總字符數)
    tts_word_progress = pyqtSignal(str)  # 當前播放的文字片段
    
    def __init__(self, config_loader=None):
        super().__init__()
        self.text_queue = queue.Queue()
        self.running = True
        self.pipeline = None
        self.current_text = ""
        self.is_speaking = False
        
        # 載入配置
        self.config = config_loader if config_loader else TTSConfigLoader()
        
        # Kokoro 設定
        self.lang_code = self.config.get_str('kokoro_lang_code', 'a')  # 'a' = American English
        self.voice = self.config.get_str('kokoro_voice', 'am_adam')  # 預設使用 Adam 男聲
        self.speed = self.config.get_float('kokoro_speed', 1.1)
        
        # 即時播放設定
        self.realtime_mode = self.config.get_bool('realtime_mode', True)
        self.min_chunk_length = self.config.get_int('min_chunk_length', 15)
        self.max_chunk_length = self.config.get_int('max_chunk_length', 50)
        
        # 語音修改設定
        if VOICE_MOD_AVAILABLE:
            self.voice_mod_config = VoiceModConfigLoader()
            self.voice_mod_enabled = self.voice_mod_config.get_bool('voice_mod_enabled', False)
            
            if self.voice_mod_enabled:
                self.voice_mod_service = VoiceModService(sample_rate=24000)
                self._init_voice_mod_settings()
                print("語音修改功能已啟用")
            else:
                self.voice_mod_service = None
                print("語音修改功能已禁用")
        else:
            self.voice_mod_service = None
            self.voice_mod_config = None
            self.voice_mod_enabled = False
            print("語音修改服務不可用")
        
        # 測試模式
        if self.config.get_bool('test_mode', False):
            print("Kokoro TTS 測試模式已啟用")
        
        # 初始化進度追蹤
        self.current_position = 0
        self.text_length = 0
        
    def _init_voice_mod_settings(self):
        """初始化語音修改設定"""
        if not self.voice_mod_service or not self.voice_mod_config:
            return
            
        # 從語音修改配置載入器載入設定
        voice_settings = self.voice_mod_config.get_voice_mod_settings()
        self.voice_mod_service.update_settings(voice_settings)
        
        # 顯示當前配置信息
        if self.voice_mod_config.get_bool('verbose_logging', True):
            profile_info = self.voice_mod_config.get_current_profile_info()
            print(f"📢 {profile_info}")
            
            # 驗證設定並顯示警告
            warnings = self.voice_mod_config.validate_settings()
            if warnings:
                print("⚠️ 語音修改設定警告:")
                for warning in warnings:
                    print(f"  - {warning}")
    
    def init_engine(self):
        """初始化 Kokoro TTS 引擎"""
        if not KOKORO_AVAILABLE:
            print("Kokoro TTS 不可用")
            return False
            
        try:
            print(f"正在初始化 Kokoro TTS (語言: {self.lang_code}, 語音: {self.voice})")
            self.pipeline = KPipeline(lang_code=self.lang_code)
            
            if self.config.get_bool('verbose_logging', True):
                print(f"Kokoro TTS 引擎設定: 語音={self.voice}, 速度={self.speed}")
                if self.realtime_mode:
                    print(f"即時模式已啟用: 分割長度 {self.min_chunk_length}-{self.max_chunk_length} 字符")
            
            # 測試模式播放測試音頻
            if self.config.get_bool('test_mode', False):
                test_text = self.config.get_str('test_text', 'Kokoro TTS test successful.')
                QTimer.singleShot(1000, lambda: self._test_speech(test_text))
            
            return True
            
        except Exception as e:
            print(f"Kokoro TTS 引擎初始化失敗: {e}")
            return False
    
    def _test_speech(self, test_text):
        """測試語音合成"""
        try:
            print(f"測試語音合成: {test_text}")
            self.add_text(test_text)
        except Exception as e:
            print(f"測試語音失敗: {e}")
    
    def add_text(self, text):
        """添加文字到語音合成佇列"""
        if text.strip():
            self.text_queue.put(text.strip())
    
    def add_text_with_original_length(self, filtered_text, original_length):
        """添加過濾後的文字到佇列，同時記錄原始長度以修復進度計算"""
        if filtered_text and filtered_text.strip():
            # 在文字前添加特殊標記來傳遞原始長度信息
            text_with_length = f"ORIGINAL_LENGTH:{original_length}|{filtered_text.strip()}"
            # 添加文字到TTS佇列
            self.text_queue.put(text_with_length)
    
    def clear_queue(self):
        """清空語音合成佇列"""
        try:
            while not self.text_queue.empty():
                self.text_queue.get_nowait()
        except queue.Empty:
            pass
    
    def stop_current(self):
        """停止當前語音合成"""
        self.is_speaking = False
        if PYGAME_AVAILABLE:
            pygame.mixer.stop()
    
    def run(self):
        """主工作循環"""
        if not self.init_engine():
            return
             
        while self.running:
            try:
                # 等待文字輸入
                text = self.text_queue.get(timeout=1.0)
                if not text or not self.running:
                    continue
                
                # 修復進度計算：解析原始長度信息
                original_text_length = None
                if text.startswith("ORIGINAL_LENGTH:"):
                    # 解析格式：ORIGINAL_LENGTH:123|實際文字
                    parts = text.split("|", 1)
                    if len(parts) == 2:
                        length_part = parts[0].replace("ORIGINAL_LENGTH:", "")
                        try:
                            original_text_length = int(length_part)
                            text = parts[1]  # 使用過濾後的文字進行TTS
                        except ValueError:
                            pass  # 解析失敗，使用原始邏輯
                
                self.current_text = text
                # 使用原始文字長度作為進度基準，確保字幕同步
                self.text_length = original_text_length if original_text_length else len(text)
                self.current_position = 0
                
                # TTS進度基準設定完成
                
                # 開始語音合成
                self.tts_started.emit()
                self.is_speaking = True
                
                # 使用 Kokoro 合成語音
                if self.realtime_mode:
                    self._synthesize_realtime(text)
                else:
                    self._synthesize_with_kokoro(text)
                
                # 確保最終進度達到100%
                if self.current_position < self.text_length:
                    self.current_position = self.text_length
                    self.tts_progress.emit(self.current_position, self.text_length)
                
                # 語音結束
                self.is_speaking = False
                self.tts_finished.emit()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.tts_error.emit(f"語音合成錯誤: {e}")
                self.is_speaking = False
                # 錯誤時也要發送完成信號，避免系統卡住
                self.tts_finished.emit()
    
    def _synthesize_realtime(self, text):
        """即時語音合成模式"""
        try:
            if not self.pipeline:
                raise Exception("Kokoro 引擎未初始化")
            
            # 智能文字分割，適合即時播放
            chunks = self._smart_split_text(text)
            total_chunks = len(chunks)
            
            cumulative_chars = 0
            
            for i, chunk in enumerate(chunks):
                if not self.running or not self.is_speaking:
                    break
                
                # 發出當前播放的文字片段信號
                self.tts_word_progress.emit(chunk)
                
                # 合成當前片段
                generator = self.pipeline(
                    chunk, 
                    voice=self.voice, 
                    speed=self.speed
                )
                
                # 計算這個片段的起始字符位置
                chunk_start_pos = cumulative_chars
                chunk_length = len(chunk)
                
                # 完整播放每個片段，確保不重疊
                for gs, ps, audio in generator:
                    if not self.running or not self.is_speaking:
                        break
                    
                    # 播放當前片段，並實時更新進度
                    self._play_audio_with_progress(audio, chunk_start_pos, chunk_length)
                
                # 片段播放完畢，強制更新到片段結束位置
                cumulative_chars += len(chunk)
                
                # 修復進度計算：按比例映射到原始文字長度
                if len(text) > 0:  # 避免除零
                    # 計算在過濾後文字中的進度比例
                    filtered_progress_ratio = min(cumulative_chars / len(text), 1.0)
                    # 映射到原始文字長度
                    progress = int(filtered_progress_ratio * self.text_length)
                else:
                    progress = self.text_length
                
                # 確保進度確實前進到片段結束
                if progress > self.current_position:
                    self.current_position = progress
                    self.tts_progress.emit(progress, self.text_length)
                
                # 💪 確保字幕完成顯示 - 大幅減少重複發送
                self.tts_progress.emit(progress, self.text_length)
                
                # 片段間最小停頓 - 進一步縮短延遲以修復句號處卡頓
                time.sleep(0.02)  # 從50ms減少到20ms，大幅改善句號處體驗
                
                print(f"⏸️ 片段間隔完成，準備下一片段")
                
                # 檢查是否需要停止
                if not self.running or not self.is_speaking:
                    break
                
        except Exception as e:
            raise Exception(f"Kokoro 即時合成失敗: {e}")
    
    def _synthesize_with_kokoro(self, text):
        """標準語音合成模式"""
        try:
            if not self.pipeline:
                raise Exception("Kokoro 引擎未初始化")
            
            # 分割文字以進行漸進式播放
            sentences = self._split_text(text)
            total_sentences = len(sentences)
            
            for i, sentence in enumerate(sentences):
                if not self.running or not self.is_speaking:
                    break
                
                # 合成單句
                generator = self.pipeline(
                    sentence, 
                    voice=self.voice, 
                    speed=float(self.speed)
                )
                
                for gs, ps, audio in generator:
                    if not self.running or not self.is_speaking:
                        break
                    
                    # 播放音訊
                    self._play_audio(audio)
                    
                    # 更新進度
                    progress = int((i + 1) / total_sentences * len(text))
                    self.current_position = progress
                    self.tts_progress.emit(progress, len(text))
                
        except Exception as e:
            raise Exception(f"Kokoro 合成失敗: {e}")
    
    def _smart_split_text(self, text):
        """改進的智能分割策略，減少句號處的延遲問題"""
        chunks = []
        
        # 🎯 關鍵修復：避免過度分割，合併短句提升流暢度
        # 只在較長的自然停頓處分割，而不是每個句號
        
        # 先按句號分割獲取基本句子
        sentences = text.split('.')
        current_chunk = ""
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 重新加回句號（除了最後一個空片段）
            if i < len(sentences) - 1:
                sentence += '.'
            elif text.rstrip().endswith('.') and sentence:
                sentence += '.'
            
            # 嘗試組合句子，避免過短的片段
            test_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence
            
            # 分割判斷邏輯：
            # 1. 如果組合後太長（超過100字符），且當前片段夠長（>30字符），就分割
            # 2. 如果當前是最後一句，就組合
            if (len(test_chunk) > 100 and len(current_chunk) > 30 and i < len(sentences) - 2):
                # 保存當前片段並開始新片段
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                # 繼續組合
                current_chunk = test_chunk
        
        # 添加最後的片段
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # 如果沒有有效片段，返回原文
        if not chunks:
            chunks = [text.strip()]
        
        # 調試信息：顯示分割結果
        if len(chunks) > 1:
            print(f"📝 TTS智能分割: {len(chunks)}個片段")
            for i, chunk in enumerate(chunks):
                print(f"  片段{i+1}: {chunk[:50]}{'...' if len(chunk) > 50 else ''} ({len(chunk)}字符)")
        else:
            print(f"📝 TTS保持完整: {len(text)}字符，無需分割")
            
        return chunks
    
    def _split_long_sentence(self, sentence):
        """分割過長的句子，保持自然語音流暢性"""
        chunks = []
        
        # 如果句子不是特別長，可以稍微容忍
        if len(sentence) <= self.max_chunk_length * 1.2:  # 允許超長20%
            return [sentence]
        
        # 對於確實很長的句子，按自然停頓點分割
        split_patterns = [
            # 1. 強分割：主要連詞處分割（保持語意完整）
            r'(\s+(?:and|but|or|so|because|although|while|when|if|unless|since|as|that|which)\s+)',
            # 2. 中分割：逗號後的轉折詞
            r'(,\s+(?:and|but|or|however|moreover|furthermore|therefore|nevertheless|meanwhile|also)\s+)',
            # 3. 較弱分割：逗號（但確保前後都有足夠內容）
            r'(,\s+(?=\w{8,}))',  # 逗號後至少8個字符
            # 4. 最後選擇：介詞短語
            r'(\s+(?:in order to|in addition to|as well as|such as)\s+)',
        ]
        
        current_text = sentence
        best_split = None
        
        # 嘗試找到最佳分割點
        for pattern in split_patterns:
            match = re.search(pattern, current_text)
            if match:
                split_pos = match.end()
                first_part = current_text[:split_pos].strip()
                remaining = current_text[split_pos:].strip()
                
                # 評估分割質量
                if (len(first_part) >= self.min_chunk_length * 2 and  # 至少是最小長度的2倍
                    len(first_part) <= self.max_chunk_length and
                    len(remaining) >= self.min_chunk_length * 2):
                    
                    best_split = (first_part, remaining)
                    break
        
        if best_split:
            first_part, remaining = best_split
            chunks.append(first_part)
            
            # 遞歸處理剩餘部分
            if len(remaining) > self.max_chunk_length:
                sub_chunks = self._split_long_sentence(remaining)
                chunks.extend(sub_chunks)
            else:
                chunks.append(remaining)
        else:
            # 沒有找到好的分割點，按詞語強制分割
            word_chunks = self._split_by_words_conservative(current_text)
            chunks.extend(word_chunks)
        
        return chunks
    
    def _split_by_words_conservative(self, text):
        """保守的按詞分割，盡量保持語音自然"""
        chunks = []
        words = text.split()
        current_chunk = ""
        
        # 更嚴格的避免結尾詞列表
        avoid_ending = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for', 'with', 'to', 'of', 'from',
            'is', 'are', 'was', 'were', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'can',
            'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
            'very', 'quite', 'rather', 'more', 'most', 'some', 'any', 'many', 'much', 'few', 'several'
        }
        
        for i, word in enumerate(words):
            test_chunk = (current_chunk + " " + word).strip()
            
            # 如果超長且當前片段夠長
            if len(test_chunk) > self.max_chunk_length and len(current_chunk) >= self.min_chunk_length * 2:
                # 檢查結尾詞
                last_word = current_chunk.strip().split()[-1].lower().rstrip('.,!?')
                
                if last_word in avoid_ending and i < len(words) - 1:
                    # 嘗試多加一個詞
                    next_word = words[i + 1] if i + 1 < len(words) else ""
                    extended_test = test_chunk + " " + next_word
                    if len(extended_test) <= self.max_chunk_length * 1.1:  # 允許超長10%
                        current_chunk = extended_test
                        continue
                
                # 確定分割
                chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk = test_chunk
        
        # 添加最後片段
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_text(self, text):
        """分割文字為句子"""
        # 依據句號、問號、驚嘆號分割
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 如果沒有分割成功，直接返回原文
        if not sentences:
            sentences = [text]
            
        return sentences
    
    def _play_audio_complete(self, audio):
        """完整播放音訊，確保每句話都完整播放完成"""
        if not PYGAME_AVAILABLE:
            return
            
        try:
            # 停止前一個音訊（如果還在播放）
            if pygame.mixer.get_busy():
                pygame.mixer.stop()
                # 短暫等待確保停止
                time.sleep(0.05)
            
            # 將 PyTorch tensor 轉換為 numpy 數組
            import numpy as np
            if hasattr(audio, 'numpy'):
                audio_np = audio.numpy()
            else:
                audio_np = audio
            
            # 確保是一維數組
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            
            # 轉換為 16 位整數格式
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            # 轉換為立體聲格式 (pygame 需要)
            stereo_audio = np.column_stack((audio_int16, audio_int16))
            
            # 使用 pygame 播放
            sound = pygame.sndarray.make_sound(stereo_audio)
            
            # 開始播放
            sound.play()
            
            # 完整等待播放結束
            while pygame.mixer.get_busy():
                if not self.running or not self.is_speaking:
                    pygame.mixer.stop()
                    break
                time.sleep(0.02)  # 短暫等待，但要完整播放
                
        except Exception as e:
            print(f"完整音訊播放錯誤: {e}")
    
    def _play_audio_quick(self, audio):
        """快速音訊播放（已停用，改用完整播放）"""
        # 改用完整播放，確保不會重疊
        self._play_audio_complete(audio)
    
    def _play_audio_blocking(self, audio):
        """阻塞音訊播放，確保按順序播放"""
        if not PYGAME_AVAILABLE:
            return
            
        try:
            # 停止所有正在播放的音訊
            pygame.mixer.stop()
            
            # 將 PyTorch tensor 轉換為 numpy 數組
            import numpy as np
            if hasattr(audio, 'numpy'):
                audio_np = audio.numpy()
            else:
                audio_np = audio
            
            # 確保是一維數組
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            
            # 轉換為 16 位整數格式
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            # 轉換為立體聲格式 (pygame 需要)
            stereo_audio = np.column_stack((audio_int16, audio_int16))
            
            # 使用 pygame 播放
            sound = pygame.sndarray.make_sound(stereo_audio)
            
            # 開始播放
            sound.play()
            
            # 等待播放完成
            while pygame.mixer.get_busy():
                if not self.running or not self.is_speaking:
                    pygame.mixer.stop()
                    break
                time.sleep(0.01)  # 短暫等待，減少 CPU 使用
                
        except Exception as e:
            print(f"阻塞音訊播放錯誤: {e}")
    
    def _play_audio_nonblocking(self, audio):
        """非阻塞音訊播放（已停用，改用阻塞播放）"""
        # 不再使用非阻塞播放，改為調用阻塞播放
        self._play_audio_blocking(audio)
    
    def _play_audio(self, audio):
        """標準音訊播放 (阻塞)"""
        if not PYGAME_AVAILABLE:
            return
            
        try:
            # 停止所有正在播放的音訊
            pygame.mixer.stop()
            
            # 將 PyTorch tensor 轉換為 numpy 數組
            import numpy as np
            if hasattr(audio, 'numpy'):
                audio_np = audio.numpy()
            else:
                audio_np = audio
            
            # 確保是一維數組
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            
            # 轉換為 16 位整數格式
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            # 轉換為立體聲格式 (pygame 需要)
            stereo_audio = np.column_stack((audio_int16, audio_int16))
            
            # 使用 pygame 播放
            sound = pygame.sndarray.make_sound(stereo_audio)
            sound.play()
            
            # 等待播放完成
            while pygame.mixer.get_busy():
                if not self.running or not self.is_speaking:
                    pygame.mixer.stop()
                    break
                time.sleep(0.01)  # 短暫等待，減少 CPU 使用
                
        except Exception as e:
            print(f"音訊播放錯誤: {e}")
    
    def get_estimated_duration(self, text):
        """估算語音持續時間（秒）"""
        # Kokoro 的估算：大約每分鐘 150 個英文字
        chars_per_minute = 150 * 5  # 大約每個英文字 5 個字符
        duration = len(text) / chars_per_minute * 60
        return duration / self.speed  # 考慮速度調整
    
    def shutdown(self):
        """關閉工作線程"""
        self.running = False
        self.clear_queue()
        if PYGAME_AVAILABLE:
            pygame.mixer.quit()

    def _play_audio_with_progress(self, audio, chunk_start_pos, chunk_length):
        """播放音訊並實時更新進度 - 優化版本"""
        if not PYGAME_AVAILABLE:
            return
            
        try:
            # 停止前一個音訊
            if pygame.mixer.get_busy():
                pygame.mixer.stop()
                time.sleep(0.02)
            
            # 轉換音訊格式
            import numpy as np
            if hasattr(audio, 'numpy'):
                audio_np = audio.numpy()
            else:
                audio_np = audio
            
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            
            audio_int16 = (audio_np * 32767).astype(np.int16)
            stereo_audio = np.column_stack((audio_int16, audio_int16))
            
            sound = pygame.sndarray.make_sound(stereo_audio)
            
            # 計算音訊時長
            sample_rate = 24000  # Kokoro TTS 採樣率
            estimated_duration = len(audio_np) / sample_rate
            
            # 開始播放
            play_start_time = time.time()
            sound.play()
            
            # 播放片段音頻
            
            # 動態更新頻率 - 接近結尾時更頻繁更新，修復短詞延遲
            base_update_interval = 0.016  # 基礎60fps更新頻率
            last_update_time = play_start_time
            
            while pygame.mixer.get_busy():
                if not self.running or not self.is_speaking:
                    pygame.mixer.stop()
                    break
                
                current_time = time.time()
                elapsed_time = current_time - play_start_time
                
                # 精確的進度計算 - 改進結尾同步
                if estimated_duration > 0:
                    progress_ratio = min(elapsed_time / estimated_duration, 1.0)
                    
                    # 更精確的結尾處理 - 避免過早完成或延遲
                    if progress_ratio > 0.85:  # 85%以後更細緻處理
                        # 使用更平滑的加速曲線
                        excess = progress_ratio - 0.85
                        acceleration = 1.0 + (excess * 0.3)  # 最多加速30%
                        progress_ratio = min(0.85 + excess * acceleration, 1.0)
                else:
                    progress_ratio = 1.0
                
                # 計算當前字符位置（在過濾後文字中）
                filtered_char_pos = chunk_start_pos + int(progress_ratio * chunk_length)
                filtered_char_pos = min(filtered_char_pos, chunk_start_pos + chunk_length)
                
                # 💪 修復進度計算：將過濾後文字位置映射到原始文字長度
                if len(self.current_text) > 0:  # 避免除零
                    # 計算在過濾後文字中的進度比例
                    filtered_progress_ratio = filtered_char_pos / len(self.current_text)
                    # 映射到原始文字長度 - 使用四捨五入而非截斷，避免丟失字符
                    target_char_pos = round(filtered_progress_ratio * self.text_length)
                else:
                    target_char_pos = self.text_length
                
                # 確保進度只前進，不後退
                if target_char_pos > self.current_position:
                    self.current_position = target_char_pos
                    self.tts_progress.emit(self.current_position, self.text_length)
                    last_update_time = current_time
                
                # 檢查是否長時間沒有進度更新 - 針對短詞末尾延遲優化
                time_since_last_update = current_time - last_update_time
                
                # 💪 修復：針對片段內部進度使用不同的超時邏輯（不是整體進度）
                if progress_ratio > 0.90:  # 片段90%以後更積極
                    timeout_threshold = 0.06  # 60ms就觸發強制完成（更積極）
                elif progress_ratio > 0.80:  # 片段80-90%之間  
                    timeout_threshold = 0.08  # 80ms觸發
                else:
                    timeout_threshold = 0.12  # 80%以前維持120ms
                
                # 🎯 關鍵修復：檢查片段內部進度，而不是整體文字進度
                if (time_since_last_update > timeout_threshold and  
                    progress_ratio > 0.75 and  # 降低到75%就開始檢查（更積極）
                    self.current_position < chunk_start_pos + chunk_length):  # 還沒完成這個片段
                    # 強制完成這個片段
                    self.current_position = chunk_start_pos + chunk_length
                    self.tts_progress.emit(self.current_position, self.text_length)
                    break
                
                # 動態調整更新頻率 - 接近結尾時更頻繁
                if progress_ratio > 0.90:  # 90%以後使用120fps
                    update_interval = 0.008
                elif progress_ratio > 0.80:  # 80-90%使用90fps  
                    update_interval = 0.011
                else:  # 80%以前使用60fps
                    update_interval = base_update_interval
                
                time.sleep(update_interval)
            
            # 💪 積極確保片段完全結束 - 修復每個句子最後幾個字符延遲
            # 🎯 關鍵修復：檢查當前片段的內部進度，而不是整個文字的進度！
            
            # 計算片段內部的進度比例（相對於這個片段）
            current_time = time.time()
            elapsed_time = current_time - play_start_time
            chunk_progress_ratio = min(elapsed_time / estimated_duration, 1.0) if estimated_duration > 0 else 1.0
            
            # 每個片段96%完成就強制至片段末尾
            if chunk_progress_ratio > 0.96:
                # 直接跳到片段結束
                final_pos = chunk_start_pos + chunk_length
            else:
                # 正常計算片段末尾位置
                final_pos = chunk_start_pos + chunk_length
            
            # 將片段位置映射到原始文字長度
            if len(self.current_text) > 0:  # 避免除零
                # 計算在過濾後文字中的進度比例
                filtered_progress_ratio = final_pos / len(self.current_text)
                # 映射到原始文字長度 - 使用四捨五入避免丟失字符
                mapped_final_pos = round(filtered_progress_ratio * self.text_length)
            else:
                mapped_final_pos = self.text_length
            
            if mapped_final_pos > self.current_position:
                self.current_position = mapped_final_pos
                
                # 立即發送片段完成信號
                self.tts_progress.emit(self.current_position, self.text_length)
            
            # 最小等待確保播放完全停止 - 進一步減少句號處延遲
            time.sleep(0.01)  # 從40ms減少到10ms，修復句號處卡頓
                
        except Exception as e:
            print(f"音訊播放錯誤: {e}")


class TTSService(QObject):
    """TTS 服務主類"""
    
    # 信號定義
    tts_started = pyqtSignal()
    tts_finished = pyqtSignal()
    tts_error = pyqtSignal(str)
    tts_progress = pyqtSignal(int, int)  # (當前字符位置, 總字符數)
    tts_word_progress = pyqtSignal(str)  # 當前播放的文字片段
    
    def __init__(self, enabled=True, config_loader=None):
        super().__init__()
        self.enabled = enabled
        self.worker = None
        self.config = config_loader if config_loader else TTSConfigLoader()
        
        # 🔥 新增：防重複播放機制
        self.last_spoken_text = ""
        self.is_currently_speaking = False
        self.speak_cooldown_timer = QTimer()
        self.speak_cooldown_timer.setSingleShot(True)
        self.speak_cooldown_timer.timeout.connect(self._reset_speaking_state)
        
        if self.enabled:
            self.init_worker()
    
    def init_worker(self):
        """初始化工作線程"""
        try:
            self.worker = KokoroTTSWorker(self.config)
            
            # 連接信號
            self.worker.tts_started.connect(self.on_tts_started)
            self.worker.tts_finished.connect(self.on_tts_finished)
            self.worker.tts_error.connect(self.on_tts_error)
            self.worker.tts_progress.connect(self.on_tts_progress)
            self.worker.tts_word_progress.connect(self.on_tts_word_progress)
            
            # 啟動工作線程
            self.worker.start()
            
            return True
            
        except Exception as e:
            print(f"TTS 工作線程初始化失敗: {e}")
            return False
    
    def speak_text(self, text):
        """朗讀文字"""
        if not self.enabled or not self.worker:
            return
        
        # 防重複播放檢查
        if self.is_currently_speaking:
            return
            
        # 過濾並處理文字
        filtered_text = self.filter_english_text(text)
        
        # 檢查是否與上次播放的文字相同
        if filtered_text == self.last_spoken_text:
            return
        
        if filtered_text:
            # 記錄當前播放的文字並設置狀態
            self.last_spoken_text = filtered_text
            self.is_currently_speaking = True
            
            # 清空現有佇列，確保只播放最新的文字
            self.worker.clear_queue()
            
            self.worker.add_text_with_original_length(filtered_text, len(text))
    
    def filter_english_text(self, text):
        """過濾和處理英文文字"""
        if not text:
            return ""
        
        # 移除多餘的空白
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 移除特殊字符但保留基本標點
        text = re.sub(r'[^\w\s.!?,-]', '', text)
        
        # 移除過短的文字
        if len(text.strip()) < 3:
            return ""
        
        return text
    
    def stop_speaking(self):
        """停止語音"""
        print("🛑 TTSService: 停止語音播放")
        if self.worker:
            self.worker.stop_current()
        # 🔥 停止時重置狀態
        self._reset_speaking_state()
        self.speak_cooldown_timer.stop()
    
    def clear_queue(self):
        """清空語音佇列"""
        if self.worker:
            self.worker.clear_queue()
    
    def on_tts_started(self):
        """TTS 開始事件"""
        print("🎵 TTSService: TTS 開始播放")
        self.is_currently_speaking = True
        self.tts_started.emit()
    
    def on_tts_finished(self):
        """TTS 結束事件"""
        print("🎵 TTSService: TTS 播放完成")
        # 🔥 設置冷卻時間，防止立即重複播放
        self.speak_cooldown_timer.start(500)  # 500ms 冷卻時間
        self.tts_finished.emit()
    
    def on_tts_error(self, error_msg):
        """TTS 錯誤事件"""
        print(f"TTS 錯誤: {error_msg}")
        # 🔥 錯誤時也要重置狀態
        self._reset_speaking_state()
        self.tts_error.emit(error_msg)
    
    def _reset_speaking_state(self):
        """重置播放狀態"""
        print("🔄 TTSService: 重置播放狀態")
        self.is_currently_speaking = False
    
    def on_tts_progress(self, current_pos, total_len):
        """TTS 進度事件"""
        self.tts_progress.emit(current_pos, total_len)
    
    def on_tts_word_progress(self, current_chunk):
        """TTS 文字片段進度事件"""
        self.tts_word_progress.emit(current_chunk)
    
    def set_enabled(self, enabled):
        """設定 TTS 啟用狀態"""
        self.enabled = enabled
        if enabled and not self.worker:
            self.init_worker()
    
    def is_available(self):
        """檢查 TTS 是否可用"""
        return KOKORO_AVAILABLE and self.worker is not None
    
    def get_estimated_duration(self, text):
        """獲取文字的估算語音時長"""
        if self.worker:
            return self.worker.get_estimated_duration(text)
        return 0
    
    def shutdown(self):
        """關閉 TTS 服務"""
        print("🔌 TTSService: 關閉 TTS 服務")
        # 🔥 關閉時停止計時器
        if hasattr(self, 'speak_cooldown_timer'):
            self.speak_cooldown_timer.stop()
        
        if self.worker:
            self.worker.shutdown()
            self.worker.wait(3000)  # 等待最多 3 秒
            if self.worker.isRunning():
                self.worker.terminate()