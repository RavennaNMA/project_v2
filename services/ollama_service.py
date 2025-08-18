# Location: project_v2/services/ollama_service.py
# Usage: Ollama AI 服務，處理圖像分析和策略生成 - 改良版本

from PyQt6.QtCore import QObject, QThread, pyqtSignal
import ollama
import base64
import json
import os
import re
import gc


class OllamaThread(QThread):
    """Ollama 執行緒 - 改良版本"""
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(str)
    
    def __init__(self, image_path, weapon_list, prompt_template, llm_timeout=10, max_retries=2):
        super().__init__()
        self.image_path = image_path
        self.weapon_list = weapon_list
        self.prompt_template = prompt_template
        self.llm_timeout = llm_timeout
        self.max_retries = max_retries
        
        self.img_model = "llava"
        self.desc_model = "jcai/llama-3-taiwan-8b-instruct:q4_k_m"
        
        # 載入禁用詞語配置
        self.forbidden_patterns = self._load_forbidden_words()
        
    def _load_forbidden_words(self):
        """載入禁用詞語配置"""
        forbidden_file = "config/forbidden_words_config.txt"
        patterns = []
        
        # 預設的基本禁用模式
        default_patterns = [
            r'Caption_TC[:：]',
            r'Caption_EN[:：]', 
            r'Weapons[:：]',
            r'Type\s*\d+',
            r'Tc[:：]',
            r'En[:：]',
            r'\d{3,}',
            r'^\d+$',
            r'\[\d+,?\s*\]',
            r'weapon\d+_id',
            r'[()（）]',
        ]
        
        patterns.extend(default_patterns)
        
        try:
            if os.path.exists(forbidden_file):
                with open(forbidden_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳過空行和註釋行
                        if line and not line.startswith('#'):
                            patterns.append(line)
                print(f"載入了 {len(patterns)} 個禁用模式")
            else:
                print("禁用詞語配置檔案不存在，使用預設模式")
        except Exception as e:
            print(f"載入禁用詞語配置錯誤: {e}")
            
        return patterns
        
    def run(self):
        """執行 AI 分析 - 增強版本"""
        import time
        
        # 記錄失敗原因供診斷
        failure_reasons = []
        image_description = None
        
        for retry in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                # 第一階段：圖像分析（只需要做一次）
                if not image_description:
                    self.progress_update.emit(f"分析圖像... (嘗試 {retry + 1}/{self.max_retries + 1})")
                    image_description = self._analyze_image()
                    
                    elapsed = time.time() - start_time
                    if elapsed > self.llm_timeout:
                        raise Exception(f"圖像分析超時 ({elapsed:.1f}秒)")

                    if not image_description:
                        raise Exception("圖像分析失敗")
                    
                    print(f"圖像分析完成: {image_description[:50]}...")
                
                # 第二階段：策略生成
                remaining_time = self.llm_timeout - (time.time() - start_time)
                if remaining_time <= 2:  # 至少保留2秒
                    remaining_time = 2
                    
                self.progress_update.emit(f"生成策略... (嘗試 {retry + 1}/{self.max_retries + 1}, 剩餘: {remaining_time:.1f}秒)")
                response = self._generate_strategy(image_description, remaining_time)
                
                # 詳細記錄回應內容供診斷
                print(f"LLM 原始回應: {response}")
                
                # 驗證回應品質
                validation_result = self._validate_response(response)
                if validation_result:
                    total_time = time.time() - start_time
                    print(f"AI 分析成功，耗時: {total_time:.1f}秒")
                    print(f"最終回應: {response}")
                    self.result_ready.emit(response)
                    return
                else:
                    failure_reason = f"回應驗證失敗 (嘗試 {retry + 1})"
                    failure_reasons.append(failure_reason)
                    
                    if retry < self.max_retries:
                        print(f"{failure_reason}，將重新生成策略...")
                        # 不重新分析圖像，只重新生成策略
                        time.sleep(0.5)  # 短暫等待
                        continue
                    else:
                        raise Exception(f"多次嘗試後回應驗證仍失敗: {'; '.join(failure_reasons)}")
                        
            except Exception as e:
                failure_reason = f"錯誤 (嘗試 {retry + 1}): {str(e)}"
                failure_reasons.append(failure_reason)
                
                if retry < self.max_retries:
                    print(f"AI 分析錯誤，準備重試... {failure_reason}")
                    time.sleep(1)  # 重試前等待
                    gc.collect()  # 釋放記憶體
                else:
                    total_time = time.time() - start_time if 'start_time' in locals() else 0
                    error_msg = f"AI 分析最終失敗 (耗時: {total_time:.1f}秒): {'; '.join(failure_reasons)}"
                    print(error_msg)
                    self.error_occurred.emit(error_msg)
                    
    def _validate_response(self, response):
        """驗證回應品質 - 增強版本"""
        if not response or not isinstance(response, dict):
            print("回應格式無效")
            return False
            
        caption_tc = response.get('caption_tc', '').strip()
        caption_en = response.get('caption_en', '').strip()
        caption = response.get('caption', '').strip()
        
        # 1. 檢查必要欄位是否存在且非空
        if not caption_tc:
            print("驗證失敗: caption_tc 為空")
            return False
            
        if not caption_en:
            print("驗證失敗: caption_en 為空")
            return False
            
        if not caption:
            print("驗證失敗: caption 為空")
            return False
        
        # 2. 檢查是否有無效標記和模式
        for pattern in self.forbidden_patterns:
            if re.search(pattern, caption_tc, re.IGNORECASE):
                print(f"驗證失敗: caption_tc 包含無效內容 '{pattern}': {caption_tc[:50]}...")
                return False
            if re.search(pattern, caption_en, re.IGNORECASE):
                print(f"驗證失敗: caption_en 包含無效內容 '{pattern}': {caption_en[:50]}...")
                return False
        
        # 3. 檢查中文內容品質
        if not self._is_primarily_chinese(caption_tc):
            print(f"驗證失敗: caption_tc 不是主要中文內容: {caption_tc[:30]}...")
            return False
            
        # 4. 檢查英文內容品質
        if caption_en and not self._is_primarily_english(caption_en):
            print(f"驗證失敗: caption_en 不是主要英文內容: {caption_en[:30]}...")
            return False
        
        # 5. 檢查字幕長度
        if len(caption_tc) < 20:
            print(f"驗證失敗: caption_tc 內容太短: {len(caption_tc)} 字")
            return False
            
        if caption_en and len(caption_en) < 20:
            print(f"驗證失敗: caption_en 內容太短: {len(caption_en)} 字")
            return False
        
        # 6. 檢查武器列表
        weapons = response.get('weapons', [])
        if not weapons:
            print("驗證失敗: 武器列表為空")
            return False
            
        if len(weapons) < 2:
            print(f"驗證失敗: 武器列表不足 (需要至少2個): {weapons}")
            return False
            
        # 檢查武器格式
        for weapon in weapons:
            if not isinstance(weapon, str) or not re.match(r'^\d{2}$', weapon):
                print(f"驗證失敗: 武器格式錯誤: {weapon}")
                return False
        
        print("回應驗證通過")
        return True
            
    def _analyze_image(self):
        """使用圖像模型分析圖片"""
        try:
            with open(self.image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
                
            print(f"呼叫 LLaVA 圖像分析模型")
            
            # 根據圖片路徑判斷是否為機器人模式
            if "robot_img" in self.image_path:
                prompt = "Describe this robot's structure and features. Focus on mechanical details, sensors, and potential capabilities. Keep it under 80 words."
            else:
                prompt = "Describe this person's appearance, clothing, and posture. Highlight unusual, contradictory, or exaggerated features. Avoid general terms. Keep it under 80 words."
                
            response = ollama.generate(
                model=self.img_model,
                prompt=prompt,
                images=[image_data],
                options={'timeout': self.llm_timeout}
            )
            
            if response and 'response' in response:
                result = response['response'].strip()
                print(f"圖像分析結果: {result[:100]}...")
                return result
                
        except Exception as e:
            print(f"圖像分析錯誤: {e}")
            
        return None
        
    def _generate_strategy(self, image_description, remaining_time=None):
        """使用語言模型生成策略 - 增強版本"""
        try:
            weapon_list_str = "\n".join([
                f"- {weapon['id']}: {weapon['name']}"
                for weapon in self.weapon_list
            ])
            
            prompt = self.prompt_template.format(
                image_description=image_description,
                weapon_list=weapon_list_str
            )
            
            timeout = remaining_time if remaining_time else self.llm_timeout
            print(f"呼叫策略生成模型 (超時: {timeout:.1f}秒)")
            print(f"發送提示詞長度: {len(prompt)} 字符")
            
            response = ollama.generate(
                model=self.desc_model,
                prompt=prompt,
                options={'timeout': timeout}
            )
            
            if response and 'response' in response:
                raw_response = response['response'].strip()
                print(f"收到原始回應長度: {len(raw_response)} 字符")
                print(f"原始回應前200字符: {raw_response[:200]}...")
                
                result = self._parse_response(raw_response)
                
                # 驗證解析結果
                if result.get('caption_tc') or result.get('caption_en'):
                    print("回應解析成功")
                else:
                    print("警告: 回應解析後缺少字幕內容")
                    
                # 釋放記憶體
                gc.collect()
                return result
            else:
                print("錯誤: LLM 回應格式異常")
                
        except Exception as e:
            print(f"策略生成錯誤: {e}")
            import traceback
            traceback.print_exc()
            
        print("使用預設回應")
        return self._get_default_response()
        
    def _parse_response(self, response_text):
        """解析 AI 回應 - 增強版本"""
        result = {
            'caption': '',
            'caption_tc': '',
            'caption_en': '',
            'weapons': []
        }
        
        if not response_text:
            return result
            
        response_text = response_text.strip()
        print(f"正在解析回應: {response_text[:100]}...")
        
        # 多種解析策略，提高成功率
        tc_patterns = [
            r'Caption_TC[:：]\s*(.*?)(?=Caption_EN[:：]|Weapons[:：]|$)',
            r'Tc[:：]\s*(.*?)(?=Caption_EN[:：]|En[:：]|Weapons[:：]|$)',
            r'繁體中文[:：]\s*(.*?)(?=Caption_EN[:：]|En[:：]|Weapons[:：]|$)',
            r'中文[:：]\s*(.*?)(?=Caption_EN[:：]|En[:：]|Weapons[:：]|$)',
        ]
        
        en_patterns = [
            r'Caption_EN[:：]\s*(.*?)(?=Weapons[:：]|$)',
            r'En[:：]\s*(.*?)(?=Weapons[:：]|$)',
            r'English[:：]\s*(.*?)(?=Weapons[:：]|$)',
            r'英文[:：]\s*(.*?)(?=Weapons[:：]|$)',
        ]
        
        # 解析中文字幕
        for pattern in tc_patterns:
            tc_match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if tc_match:
                caption_tc = self._clean_caption_text(tc_match.group(1))
                if caption_tc and self._is_primarily_chinese(caption_tc) and len(caption_tc) >= 20:
                    result['caption_tc'] = caption_tc[:180]
                    print(f"解析到中文字幕: {caption_tc[:30]}...")
                    break
        
        # 如果沒有找到中文，嘗試從整段文字中提取中文部分
        if not result['caption_tc']:
            print("嘗試從全文提取中文內容...")
            lines = response_text.split('\n')
            for line in lines:
                cleaned_line = self._clean_caption_text(line)
                if cleaned_line and self._is_primarily_chinese(cleaned_line) and len(cleaned_line) >= 20:
                    result['caption_tc'] = cleaned_line[:180]
                    print(f"從全文提取中文字幕: {cleaned_line[:30]}...")
                    break
        
        # 最後補救：如果仍然沒有中文字幕，但有英文字幕，嘗試簡單翻譯或使用預設中文
        if not result['caption_tc'] and result['caption_en']:
            print("嘗試補救空的中文字幕...")
            # 簡單的應急中文字幕
            default_tc_templates = [
                "目標特徵分析完成，建議使用指定武器進行防禦。",
                "根據目標外觀特點，制定相應的戰術策略。",
                "分析目標弱點，選擇最佳應對方案。"
            ]
            result['caption_tc'] = default_tc_templates[0]
            print(f"使用應急中文字幕: {result['caption_tc']}")
                
        # 解析英文字幕
        for pattern in en_patterns:
            en_match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if en_match:
                caption_en = self._clean_caption_text(en_match.group(1))
                if caption_en and self._is_primarily_english(caption_en) and len(caption_en) >= 20:
                    result['caption'] = caption_en[:800]
                    result['caption_en'] = caption_en[:800]
                    print(f"解析到英文字幕: {caption_en[:30]}...")
                    break
        
        # 如果沒有找到英文，嘗試從整段文字中提取英文部分
        if not result['caption_en']:
            print("嘗試從全文提取英文內容...")
            lines = response_text.split('\n')
            for line in lines:
                cleaned_line = self._clean_caption_text(line)
                if cleaned_line and self._is_primarily_english(cleaned_line) and len(cleaned_line) >= 20:
                    result['caption'] = cleaned_line[:800]
                    result['caption_en'] = cleaned_line[:800]
                    print(f"從全文提取英文字幕: {cleaned_line[:30]}...")
                    break
        
        # 最後補救：如果仍然沒有英文字幕，但有中文字幕，使用預設英文
        if not result['caption_en'] and result['caption_tc']:
            print("嘗試補救空的英文字幕...")
            # 簡單的應急英文字幕
            default_en_templates = [
                "Target analysis completed. Recommended defensive strategy with selected weapons.",
                "Strategic assessment based on target characteristics and optimal countermeasures.",
                "Tactical analysis identifies key vulnerabilities and appropriate response protocol."
            ]
            result['caption'] = default_en_templates[0]
            result['caption_en'] = default_en_templates[0]
            print(f"使用應急英文字幕: {result['caption_en']}")
        
        # 解析武器列表 - 多種格式支援
        weapons_patterns = [
            r'Weapons[:：]\s*\[?([^\]]*)\]?',
            r'武器[:：]\s*\[?([^\]]*)\]?',
            r'Tools[:：]\s*\[?([^\]]*)\]?',
            r'\[(\d+(?:\s*,\s*\d+)*)\]',  # 純數字列表
        ]
        
        for pattern in weapons_patterns:
            weapons_match = re.search(pattern, response_text, re.IGNORECASE)
            if weapons_match:
                weapons_str = weapons_match.group(1).strip()
                weapons = []
                
                # 提取數字
                for part in re.findall(r'\d+', weapons_str):
                    if part.isdigit() and 1 <= int(part) <= 10:
                        weapons.append(f"{int(part):02d}")
                        
                if weapons:
                    result['weapons'] = weapons[:3]
                    print(f"解析到武器列表: {result['weapons']}")
                    break
        
        # 如果還是沒有武器，嘗試從全文找數字
        if not result['weapons']:
            print("嘗試從全文提取武器代號...")
            all_numbers = re.findall(r'\b(\d{1,2})\b', response_text)
            weapons = []
            for num in all_numbers:
                if num.isdigit() and 1 <= int(num) <= 10:
                    weapons.append(f"{int(num):02d}")
            if weapons:
                result['weapons'] = list(dict.fromkeys(weapons))[:3]  # 去重並限制3個
                print(f"從全文提取武器: {result['weapons']}")
            else:
                result['weapons'] = self._get_default_weapons()
                print("使用預設武器列表")
        
        # 確保武器列表至少有2個項目
        if len(result['weapons']) < 2:
            print(f"武器列表不足，補充預設武器: {result['weapons']}")
            default_weapons = self._get_default_weapons()
            # 補充缺少的武器
            for weapon in default_weapons:
                if weapon not in result['weapons']:
                    result['weapons'].append(weapon)
                if len(result['weapons']) >= 3:
                    break
            print(f"補充後武器列表: {result['weapons']}")
            
        return result
        
    def _clean_caption_text(self, text):
        """清理字幕文本 - 增強版本"""
        if not text:
            return ""
            
        # 使用配置檔案中的禁用模式來清理文本
        for pattern in self.forbidden_patterns:
            try:
                # 針對不同類型的模式使用不同的清理方式
                if pattern in [r'[()（）]', r'[（(][^)）]*[)）]']:
                    # 括號處理
                    text = re.sub(r'[（(][^)）]*[)）]', '', text)  # 移除括號內容
                    text = re.sub(r'[()（）]', '', text)  # 移除剩餘括號
                elif pattern.endswith('[:：]') or 'Caption' in pattern or 'Weapons' in pattern:
                    # 標籤處理
                    text = re.sub(pattern + r'\s*', '', text, flags=re.IGNORECASE)
                else:
                    # 一般模式直接移除
                    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            except re.error:
                # 如果正則表達式無效，嘗試作為普通字符串處理
                text = text.replace(pattern, '')
                
        # 額外的清理
        text = re.sub(r'^\d+[.,;:]*\s*', '', text)  # 移除開頭的數字
        text = re.sub(r'\s*\d+[.,;:]*$', '', text)  # 移除結尾的數字
        text = re.sub(r'，\s*，', '，', text)  # 移除重複逗號
        text = re.sub(r'\.\s*\.', '.', text)  # 移除重複句號
        text = re.sub(r'\s+', ' ', text)  # 合併多個空格
        text = text.strip(' .,;:，。、')  # 移除首尾標點
        
        # 確保文本不是純數字、純標點或純空白
        if re.match(r'^[\d\s.,;:，。、（）()\[\]]*$', text):
            return ""
            
        # 移除過短的無意義片段
        if len(text.replace(' ', '')) < 3:
            return ""
            
        return text
        
    def _is_primarily_chinese(self, text):
        """檢查文本是否主要為中文"""
        if not text:
            return False
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        return total_chars > 0 and (chinese_chars / total_chars) > 0.5
        
    def _is_primarily_english(self, text):
        """檢查文本是否主要為英文"""
        if not text:
            return False
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
        return total_chars > 0 and (english_chars / total_chars) > 0.5
        
    def _get_default_weapons(self):
        """取得預設武器列表"""
        return ['01', '02', '03']  # 增加第三個武器確保有足夠選擇
        
    def _get_default_response(self):
        """取得預設回應"""
        return {
            'caption': 'Defense protocol activated. Strategic analysis initiated with selected countermeasures.',
            'caption_tc': '防禦協議已啟動。戰略分析開始，已選定對應的防禦措施。',
            'caption_en': 'Defense protocol activated. Strategic analysis initiated with selected countermeasures.',
            'weapons': self._get_default_weapons()
        }


class OllamaService(QObject):
    """Ollama 服務管理器 - 改良版本"""
    
    analysis_complete = pyqtSignal(dict)
    analysis_error = pyqtSignal(str)
    progress_update = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.thread = None
        self.prompt_template = self._load_prompt_template()
        self.robot_prompt_template = self._load_robot_prompt_template()
        self.current_prompt = self.prompt_template
        
    def _load_prompt_template(self):
        """載入正常提示詞模板"""
        template_path = "config/prompt_config.txt"
        
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """You are analyzing a person in a survival scenario based on their appearance.

Image description: {image_description}

Available defensive tools:
{weapon_list}

Based on the person's characteristics, select 2-3 most suitable defensive tools and provide survival advice.

Response format:
Caption_TC: [繁體中文生存策略，80字內]
Caption_EN: [English survival strategy, within 80 words]
Weapons: [weapon1_id, weapon2_id, weapon3_id]"""

    def _load_robot_prompt_template(self):
        """載入機器人提示詞模板"""
        template_path = "config/robotprompt_config.txt"
        
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """You are analyzing a robot intruder that has infiltrated the defense system.

Robot description: {image_description}

Available defensive tools:
{weapon_list}

Analyze the robot's vulnerabilities and select 2-3 most effective countermeasures.

Response format:
Caption_TC: [繁體中文機器人對抗策略，80字內]
Caption_EN: [English robot countermeasure strategy, within 80 words]
Weapons: [weapon1_id, weapon2_id, weapon3_id]"""

    def load_normal_prompt(self):
        """載入正常prompt"""
        self.current_prompt = self.prompt_template
        print("Loaded normal prompt template")
        
    def load_robot_prompt(self):
        """載入機器人prompt"""
        self.current_prompt = self.robot_prompt_template
        print("Loaded robot prompt template")
        
    def analyze_image(self, image_path, weapon_list, llm_timeout=10):
        """分析圖像 - 改良版本"""
        if self.thread and self.thread.isRunning():
            print("LLM 分析已在進行中，跳過新請求")
            return
            
        # 釋放之前的記憶體
        gc.collect()
        
        print(f"Ollama Service: 開始分析圖像，超時: {llm_timeout}秒")
        self.thread = OllamaThread(
            image_path, 
            weapon_list, 
            self.current_prompt, 
            llm_timeout,
            max_retries=3  # 最多重試3次，提高成功率
        )
        self.thread.result_ready.connect(self._handle_result)
        self.thread.error_occurred.connect(self._handle_error)
        self.thread.progress_update.connect(self.progress_update.emit)
        self.thread.start()
        
    def _handle_result(self, result):
        """處理成功結果"""
        self.analysis_complete.emit(result)
        # 釋放記憶體
        gc.collect()
        
    def _handle_error(self, error):
        """處理錯誤"""
        print(f"Ollama 錯誤: {error}")
        
        # 提供預設回應
        default_response = {
            'caption': 'System analysis unavailable. Activating default protocol with selected countermeasures.',
            'caption_tc': '系統分析不可用。啟動預設協議，已選定對應的防禦措施。',
            'caption_en': 'System analysis unavailable. Activating default protocol with selected countermeasures.',
            'weapons': ['01', '02', '03']
        }
        
        self.analysis_complete.emit(default_response)
        # 釋放記憶體
        gc.collect()

