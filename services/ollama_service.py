# Location: project_v2/services/ollama_service.py
# Usage: Ollama AI 服務，處理圖像分析和策略生成

from PyQt6.QtCore import QObject, QThread, pyqtSignal
import ollama
import base64
import json
import os
import re


class OllamaThread(QThread):
    """Ollama 執行緒"""
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(str)
    
    def __init__(self, image_path, weapon_list, prompt_template, llm_timeout=10):
        super().__init__()
        self.image_path = image_path
        self.weapon_list = weapon_list
        self.prompt_template = prompt_template
        self.llm_timeout = llm_timeout  # LLM回應超時時間（秒）
        
        # 模型設定
        self.img_model = "llava"
        self.desc_model = "jcai/llama-3-taiwan-8b-instruct:q4_k_m"
        
    def run(self):
        """執行 AI 分析 - 帶超時控制"""
        import threading
        import time
        
        start_time = time.time()
        
        try:
            # 第一階段：圖像分析
            self.progress_update.emit(f"正在分析圖像... (超時: {self.llm_timeout}秒)")
            image_description = self._analyze_image()
            
            # 檢查是否超時
            elapsed = time.time() - start_time
            if elapsed > self.llm_timeout:
                raise Exception(f"圖像分析超時 ({elapsed:.1f}秒)")
            
            if not image_description:
                raise Exception("圖像分析失敗")
                
            # 第二階段：策略生成
            remaining_time = self.llm_timeout - elapsed
            if remaining_time <= 0:
                raise Exception(f"總處理時間已超時 ({elapsed:.1f}秒)")
                
            self.progress_update.emit(f"正在生成策略... (剩餘時間: {remaining_time:.1f}秒)")
            response = self._generate_strategy(image_description, remaining_time)
            
            total_time = time.time() - start_time
            print(f"AI 分析完成，總耗時: {total_time:.1f}秒")
            self.result_ready.emit(response)
            
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"{str(e)} (總耗時: {total_time:.1f}秒)"
            print(f"AI 分析錯誤: {error_msg}")
            self.error_occurred.emit(error_msg)
            
    def _analyze_image(self):
        """使用圖像模型分析圖片 - 帶超時控制"""
        try:
            # 讀取圖片並轉換為 base64
            with open(self.image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
                
            print(f"呼叫 LLaVA 圖像分析模型 (超時: {self.llm_timeout}秒)")
            
            # 呼叫 llava 模型 - 添加超時控制
            response = ollama.generate(
                model=self.img_model,
                prompt="Describe this person’s appearance, clothing, and posture. Highlight unusual, contradictory, or exaggerated features. Avoid general terms. Keep it under 80 words.",
                images=[image_data],
                options={'timeout': self.llm_timeout}
            )
            
            if response and 'response' in response:
                # 在控制台輸出 llava 模型回應
                print(f"\n=== LLAVA (img_model) Response ===")
                print(response['response'])
                print("=" * 50)
                return response['response']
                
        except Exception as e:
            print(f"圖像分析錯誤: {e}")
            
        return None
        
    def _generate_strategy(self, image_description, remaining_time=None):
        """使用語言模型生成策略 - 帶超時控制"""
        try:
            # 準備武器列表
            weapon_list_str = "\n".join([
                f"- {weapon['id']}: {weapon['name']}"
                for weapon in self.weapon_list
            ])
            
            # 填充提示詞模板
            prompt = self.prompt_template.format(
                image_description=image_description,
                weapon_list=weapon_list_str
            )
            
            # 輸出完整提示詞用於調試
            print(f"\n=== 發送給 LLM2 的完整提示詞 ===")
            print(prompt)
            print("=" * 80)
            
            # 計算超時時間
            timeout = remaining_time if remaining_time else self.llm_timeout
            print(f"呼叫策略生成模型 (超時: {timeout:.1f}秒)")
            
            # 呼叫策略模型 - 添加超時控制
            response = ollama.generate(
                model=self.desc_model,
                prompt=prompt,
                options={'timeout': timeout}
            )
            
            if response and 'response' in response:
                # 在控制台輸出 desc_model 回應
                print(f"\n=== DESC_MODEL Response ===")
                print(response['response'])
                print("=" * 60)
                
                # 解析回應
                return self._parse_response(response['response'])
                
        except Exception as e:
            print(f"策略生成錯誤: {e}")
            
        # 返回預設回應
        return {
            'caption': 'Defense protocol activated.',
            'caption_tc': '防禦協議已啟動。',
            'weapons': ['01', '02']
        }
        
    def _parse_response(self, response_text):
        """解析 AI 回應 - 支援分段同步格式"""
        result = {
            'caption': '',
            'caption_tc': '',
            'caption_en': '',  # 
            'caption_segments': [],  # 英文分段
            'caption_tc_segments': [],  # 中文分段
            'weapons': []
        }
        
        # 先移除多餘的空白和換行
        response_text = response_text.strip()
        print(f"DEBUG: 原始回應文本:\n{response_text}")
        
        # 新格式：檢查是否有分段格式
        tc_segments_match = re.search(r'Caption_TC_Segments[:：]\s*\[(.*?)\]', response_text, re.DOTALL | re.IGNORECASE)
        en_segments_match = re.search(r'Caption_EN_Segments[:：]\s*\[(.*?)\]', response_text, re.DOTALL | re.IGNORECASE)
        
        if tc_segments_match and en_segments_match:
            # 新的分段格式
            print("DEBUG: 檢測到分段同步格式")
            
            # 解析中文分段
            tc_segments_raw = tc_segments_match.group(1).strip()
            tc_segments = [seg.strip() for seg in tc_segments_raw.split('|') if seg.strip()]
            
            # 解析英文分段
            en_segments_raw = en_segments_match.group(1).strip()
            en_segments = [seg.strip() for seg in en_segments_raw.split('|') if seg.strip()]
            
            # 清理分段
            result['caption_tc_segments'] = [self._clean_caption_text(seg) for seg in tc_segments if self._clean_caption_text(seg)]
            result['caption_segments'] = [self._clean_caption_text(seg) for seg in en_segments if self._clean_caption_text(seg)]
            
            # 組合成完整字幕
            if result['caption_tc_segments']:
                result['caption_tc'] = ' '.join(result['caption_tc_segments'])
            if result['caption_segments']:
                result['caption'] = ' '.join(result['caption_segments'])
                result['caption_en'] = result['caption']  # 🔥 同步 caption_en
                
            print(f"DEBUG: 解析到分段 - 中文: {len(result['caption_tc_segments'])}段, 英文: {len(result['caption_segments'])}段")
            
        else:
            # 舊格式兼容性處理
            print("DEBUG: 使用舊格式解析")
            
            # 使用原有的正則表達式強制分離中英文內容
            tc_match = re.search(r'Caption_TC[:：]\s*(.*?)(?=Caption_EN[:：]|Weapons[:：]|$)', response_text, re.DOTALL | re.IGNORECASE)
            if tc_match:
                caption_tc_raw = tc_match.group(1).strip()
                caption_tc = re.sub(r'Caption_EN[:：].*', '', caption_tc_raw, flags=re.DOTALL | re.IGNORECASE)
                caption_tc_cleaned = self._clean_caption_text(caption_tc)
                
                if caption_tc_cleaned and self._is_primarily_chinese(caption_tc_cleaned):
                    result['caption_tc'] = caption_tc_cleaned[:180]
                    
            # 解析英文
            en_match = re.search(r'Caption_EN[:：]\s*(.*?)(?=Weapons[:：]|$)', response_text, re.DOTALL | re.IGNORECASE)
            if en_match:
                caption_en_raw = en_match.group(1).strip()
                caption_en_cleaned = self._clean_caption_text(caption_en_raw)
                
                if caption_en_cleaned and self._is_primarily_english(caption_en_cleaned):
                    result['caption'] = caption_en_cleaned[:800]
                    result['caption_en'] = caption_en_cleaned[:800]  # 🔥 添加 caption_en 同步
        
        # 解析武器列表（與之前相同）
        weapons_match = re.search(r'Weapons[:：]\s*\[?([^\]]*)\]?', response_text, re.IGNORECASE)
        if weapons_match:
            weapons_str = weapons_match.group(1).strip()
            weapons = []
            
            for part in re.findall(r'\d+', weapons_str):
                if part.isdigit() and 1 <= int(part) <= 10:
                    weapons.append(f"{int(part):02d}")
                    
            result['weapons'] = weapons[:3] if weapons else ['01', '02']
        else:
            result['weapons'] = ['01', '02']
        
        # 調試輸出
        print(f"DEBUG: 解析結果:")
        print(f"  caption_tc: '{result['caption_tc']}'")
        print(f"  caption_tc_segments: {result['caption_tc_segments']}")
        print(f"  caption: '{result['caption']}'")
        print(f"  caption_en: '{result['caption_en']}'")  # 🔥 添加調試輸出
        print(f"  caption_segments: {result['caption_segments']}")
        print(f"  weapons: {result['weapons']}")
            
        return result
        
    def _clean_caption_text(self, text):
        """清理字幕文本，移除格式標籤但保留內容"""
        if not text:
            return text
            
        # 移除格式標籤（但不移除內容描述）
        text = re.sub(r'Caption_TC[:：]\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Caption_EN[:：]\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Weapons[:：]\s*\[.*?\]', '', text, flags=re.IGNORECASE)
        
        # 只移除明顯的武器列表格式，但保留內容描述
        text = re.sub(r'\[[\d\s,]+\]$', '', text)  # 只移除結尾的數字列表
        text = re.sub(r'weapon\d+_id', '', text, flags=re.IGNORECASE)
        
        # 清理多餘的空白
        text = re.sub(r'\s+', ' ', text)  # 多個空格合併為一個
        text = re.sub(r'^[,\s]*', '', text)  # 移除開頭的逗號和空格
        text = re.sub(r'[,\s]*$', '', text)  # 移除結尾的逗號和空格
        
        # 基本標點符號清理（更保守）
        text = re.sub(r'\.+', '.', text)  # 多個句號合併為一個
        text = re.sub(r'^\.\s*', '', text)  # 移除開頭的句號
        
        # 如果整個文本只剩下標點符號，返回空字符串
        if re.match(r'^[.,;:\s]*$', text):
            return ''
        
        return text.strip()
        
    def _is_primarily_chinese(self, text):
        """檢查文本是否主要為中文"""
        if not text:
            return False
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        return total_chars > 0 and (chinese_chars / total_chars) > 0.7
        
    def _is_primarily_english(self, text):
        """檢查文本是否主要為英文"""
        if not text:
            return False
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        return total_chars > 0 and (english_chars / total_chars) > 0.7


class OllamaService(QObject):
    """Ollama 服務管理器"""
    
    analysis_complete = pyqtSignal(dict)
    analysis_error = pyqtSignal(str)
    progress_update = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.thread = None
        self.prompt_template = self._load_prompt_template()
        
    def _load_prompt_template(self):
        """載入提示詞模板"""
        template_path = "config/prompt_config.txt"
        
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # 預設模板
            return """You are analyzing a person in a survival scenario based on their appearance.

Image description: {image_description}

Available defensive tools:
{weapon_list}

Based on the person's characteristics, select 2-3 most suitable defensive tools and provide survival advice.

Response format:
Caption_TC: [繁體中文生存策略，80字內]
Caption_EN: [English survival strategy, within 80 words]
Weapons: [weapon1_id, weapon2_id, weapon3_id]"""

    def analyze_image(self, image_path, weapon_list, llm_timeout=10):
        """分析圖像 - 支援自定義超時設定"""
        if self.thread and self.thread.isRunning():
            return
            
        print(f"Ollama Service: 開始分析圖像，LLM超時設定: {llm_timeout}秒")
        self.thread = OllamaThread(image_path, weapon_list, self.prompt_template, llm_timeout)
        self.thread.result_ready.connect(self.analysis_complete.emit)
        self.thread.error_occurred.connect(self._handle_error)
        self.thread.progress_update.connect(self.progress_update.emit)
        self.thread.start()
        
    def _handle_error(self, error):
        """處理錯誤"""
        print(f"Ollama 錯誤: {error}")
        
        # 使用預設回應 - 修復：使用正確的鍵名確保TTS正常工作
        default_response = {
            'caption_en': 'System analysis unavailable. Activating default protocol.',  # 修復：使用caption_en
            'caption_tc': '系統分析不可用。啟動預設協議。',
            'caption': 'System analysis unavailable. Activating default protocol.',  # 保留兼容性
            'weapons': ['01', '02']
        }
        
        self.analysis_complete.emit(default_response)