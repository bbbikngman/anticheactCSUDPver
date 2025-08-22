# 文件: brain_ai_module.py

from openai import OpenAI
from typing import Generator, Optional, Dict, Any
import random
import time
import httpx
import json
from . import config
from .prompts import (
    PERSONA_PROMPT_V2,
    OPENING_PROMPT_TEMPLATE,
    WHISPER_PROMPT,
    ERROR_RESPONSES,
    RANDOM_ELEMENTS
)

class KimiAI:
    """封装Kimi大模型调用，管理多轮对话历史。"""

    def __init__(self, max_context_messages: int = 50, use_cache: bool = True):
        try:
            self.client = OpenAI(
                api_key=config.MOONSHOT_API_KEY,
                base_url="https://api.moonshot.cn/v1",
            )
            self.conversation_history = []
            self.max_context_messages = max_context_messages
            self.system_messages = [{"role": "system", "content": PERSONA_PROMPT_V2}]

            # 缓存相关
            self.use_cache = use_cache
            self.cache_tag = "antifraud_system_prompt"
            self.cache_ttl = 3600  # 1小时
            self.cached_system_ready = False

            if self.use_cache:
                self._setup_system_cache()

            print(f"Kimi AI大脑初始化成功 (V2口语优化版，上下文限制: {max_context_messages}条，缓存: {'启用' if use_cache else '禁用'})。")
        except Exception as e:
            print(f"Kimi AI初始化失败: {e}")
            raise

    def _chat_with_retry(self, messages: list, max_attempts: int = 100) -> Generator[str, None, None]:
        """带重试机制的聊天完成"""
        import time

        st_time = time.time()

        for attempt in range(max_attempts):
            print(f"HTTP尝试: {attempt+1}/{max_attempts}")
            try:
                response = self.client.chat.completions.create(
                    model=config.KIMI_MODEL_NAME,
                    messages=messages,
                    temperature=config.KIMI_TEMPERATURE,
                    max_tokens=config.KIMI_MAX_TOKENS,
                    stream=True
                )

                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content

                ed_time = time.time()
                print(f"HTTP查询成功! 耗时: {ed_time-st_time:.2f}秒")
                return

            except Exception as e:
                print(f"HTTP尝试 {attempt+1} 失败: {e}")
                if attempt < max_attempts - 1:
                    print("1秒后重试...")
                    time.sleep(1)
                else:
                    print("HTTP查询失败，已达到最大重试次数")
                    yield ERROR_RESPONSES["api_error"]
                    return

    def _setup_system_cache(self):
        """设置系统提示词缓存"""
        try:
            print("🗄️ 正在设置系统提示词缓存...")

            headers = {
                "Authorization": f"Bearer {config.MOONSHOT_API_KEY}",
                "Content-Type": "application/json"
            }

            cache_data = {
                "model": "moonshot-v1-128k",  # 缓存API使用的模型名称
                "messages": self.system_messages,
                "ttl": self.cache_ttl,
                "tags": [self.cache_tag]
            }

            response = httpx.post(
                f"{self.client.base_url}caching",
                headers=headers,
                json=cache_data,
                timeout=30.0
            )

            if response.status_code == 200:
                self.cached_system_ready = True
                print(f"✅ 系统提示词缓存设置成功 (标签: {self.cache_tag}, TTL: {self.cache_ttl}s)")
            else:
                print(f"⚠️ 缓存设置失败: {response.status_code} - {response.text}")
                self.use_cache = False

        except Exception as e:
            print(f"⚠️ 缓存设置异常: {e}")
            self.use_cache = False

    def _get_cached_messages(self, user_messages: list) -> list:
        """获取使用缓存的消息列表"""
        if self.use_cache and self.cached_system_ready:
            # 使用缓存引用替代系统消息
            cached_messages = [
                {
                    "role": "cache",
                    "content": f"tag={self.cache_tag};reset_ttl={self.cache_ttl}"
                }
            ]
            cached_messages.extend(user_messages)
            return cached_messages
        else:
            # 不使用缓存，包含完整系统消息
            full_messages = []
            full_messages.extend(self.system_messages)
            full_messages.extend(user_messages)
            return full_messages

    def _refresh_cache_if_needed(self):
        """根据需要刷新缓存"""
        if self.use_cache and not self.cached_system_ready:
            print("🔄 尝试重新设置缓存...")
            self._setup_system_cache()

    def _make_messages(self, user_input: str = None) -> list:
        """构建消息列表，控制上下文长度，支持缓存"""
        # 如果有用户输入，添加到历史
        if user_input:
            self.conversation_history.append({"role": "user", "content": user_input})

        # 控制历史消息长度
        if len(self.conversation_history) > self.max_context_messages:
            # 只保留最新的消息
            self.conversation_history = self.conversation_history[-self.max_context_messages:]
            print(f"📝 上下文已截断，保留最新 {self.max_context_messages} 条消息")

        # 使用缓存构建消息
        return self._get_cached_messages(self.conversation_history)

    def _chat_with_partial_mode(self, messages: list, partial_content: str = "",
                               partial_name: str = "", max_attempts: int = 100) -> Generator[str, None, None]:
        """支持部分模式的聊天完成"""
        import time

        # 如果有部分内容，添加到消息末尾
        if partial_content or partial_name:
            partial_message = {
                "role": "assistant",
                "partial": True,
                "content": partial_content
            }
            if partial_name:
                partial_message["name"] = partial_name

            messages.append(partial_message)
            print(f"🎭 启用部分模式: name='{partial_name}', content='{partial_content}'")

        st_time = time.time()

        for attempt in range(max_attempts):
            print(f"HTTP尝试: {attempt+1}/{max_attempts}")
            try:
                response = self.client.chat.completions.create(
                    model=config.KIMI_MODEL_NAME,
                    messages=messages,
                    temperature=config.KIMI_TEMPERATURE,
                    max_tokens=config.KIMI_MAX_TOKENS,
                    stream=True
                )

                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content

                ed_time = time.time()
                print(f"HTTP查询成功! 耗时: {ed_time-st_time:.2f}秒")

                # 如果使用了部分模式，需要合并完整内容
                if partial_content:
                    full_response = partial_content + full_response

                return full_response

            except Exception as e:
                print(f"HTTP尝试 {attempt+1} 失败: {e}")
                if attempt < max_attempts - 1:
                    print("1秒后重试...")
                    time.sleep(1)
                else:
                    print("HTTP查询失败，已达到最大重试次数")
                    yield ERROR_RESPONSES["api_error"]
                    return ""

    def generate_opening_statement(self) -> Generator[str, None, None]:
        """生成动态开场白"""
        try:
            # 生成随机元素
            carrier = random.choice(RANDOM_ELEMENTS["carriers"])
            hour = random.choice(RANDOM_ELEMENTS["hours"])
            country_code = random.choice(RANDOM_ELEMENTS["country_codes"])
            last_digits = random.randint(*RANDOM_ELEMENTS["digit_range"])
            
            # 构建开场白提示
            opening_prompt = OPENING_PROMPT_TEMPLATE.format(
                carrier=carrier,
                hour=hour,
                country_code=country_code,
                last_digits=last_digits
            )
            
            # 使用上下文管理构建消息
            messages = self._make_messages(opening_prompt)

            # 收集完整回复用于历史记录
            full_response = ""
            for chunk in self._chat_with_retry(messages):
                full_response += chunk
                yield chunk

            # 添加到对话历史
            if full_response:
                self.conversation_history.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            print(f"开场白生成失败: {e}")
            yield ERROR_RESPONSES["opening_error"]

    def _detect_urgent_scenario(self, user_input: str) -> Dict[str, Any]:
        """检测紧急场景，决定是否使用部分模式"""
        urgent_keywords = ["转账", "汇款", "验证码", "银行卡", "密码", "身份证", "下载", "APP", "链接", "扫码"]
        comfort_keywords = ["害怕", "担心", "紧张", "不知道", "怎么办", "慌"]

        # 检测高危操作
        if any(keyword in user_input for keyword in urgent_keywords):
            return {
                "use_partial": True,
                "partial_content": "请立即停止操作！",
                "reason": "检测到高危操作关键词"
            }

        # 检测需要安抚的情绪
        if any(keyword in user_input for keyword in comfort_keywords):
            return {
                "use_partial": True,
                "partial_content": "请您不要担心，",
                "reason": "检测到需要安抚的情绪"
            }

        # 默认使用专业身份
        return {
            "use_partial": True,
            "partial_name": "反诈专员",
            "partial_content": "",
            "reason": "使用专业身份"
        }

    def get_response_stream(self, user_input: str, use_partial_mode: bool = False,
                           partial_content: str = "", partial_name: str = "") -> Generator[str, None, None]:
        """获取AI回复的流式响应"""
        try:
            # 刷新缓存（如果需要）
            self._refresh_cache_if_needed()

            # API环境下默认不使用部分模式（避免双重请求延迟）
            if use_partial_mode:
                print("⚠️ 注意：部分模式会增加API请求延迟，建议仅在本地GPU环境使用")

            # 使用上下文管理构建消息
            messages = self._make_messages(user_input)

            # 收集完整回复
            full_response = ""

            if use_partial_mode:
                for chunk in self._chat_with_partial_mode(messages, partial_content, partial_name):
                    full_response += chunk
                    yield chunk
            else:
                for chunk in self._chat_with_retry(messages):
                    full_response += chunk
                    yield chunk

            # 添加AI回复到历史
            if full_response:
                self.conversation_history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            print(f"HTTP AI回复生成失败: {e}")
            yield ERROR_RESPONSES["api_error"]

    def get_conversation_summary(self) -> str:
        """获取对话摘要"""
        if not self.conversation_history:
            return "暂无对话历史"

        total_messages = len(self.conversation_history)
        user_messages = len([msg for msg in self.conversation_history if msg["role"] == "user"])
        assistant_messages = len([msg for msg in self.conversation_history if msg["role"] == "assistant"])

        return f"对话历史: {total_messages}条消息 (用户: {user_messages}, AI: {assistant_messages})"

    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
        print("📝 对话历史已清空")

class BrainAIModule:
    """AI大脑模块，负责生成智能回复"""
    
    def __init__(self):
        self.kimi = KimiAI()
    
    def generate_opening_statement(self) -> Generator[str, None, None]:
        """生成开场白"""
        return self.kimi.generate_opening_statement()
    
    def get_response_stream(self, user_input: str) -> Generator[str, None, None]:
        """获取对用户输入的回复"""
        return self.kimi.get_response_stream(user_input)
