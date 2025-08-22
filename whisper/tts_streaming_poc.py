#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS流式优化概念验证 - 句子级流式处理
这个POC展示了如何让WebSocket的优势真正体现出来
"""

import re
import time
import threading
from typing import Generator
import queue

class StreamingTTSProcessor:
    """流式TTS处理器 - 句子级别的实时处理"""
    
    def __init__(self):
        self.sentence_queue = queue.Queue()
        self.is_processing = False
        self.sentence_patterns = [
            r'[。！？]',  # 中文句号、感叹号、问号
            r'[.!?]',    # 英文句号、感叹号、问号
        ]
        
    def detect_sentence_end(self, text: str) -> bool:
        """检测是否包含句子结束符"""
        for pattern in self.sentence_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def extract_complete_sentences(self, text: str) -> tuple:
        """提取完整句子和剩余文本"""
        # 找到所有句子结束位置
        end_positions = []
        for pattern in self.sentence_patterns:
            for match in re.finditer(pattern, text):
                end_positions.append(match.end())
        
        if not end_positions:
            return "", text
        
        # 找到最后一个句子结束位置
        last_end = max(end_positions)
        complete_sentences = text[:last_end].strip()
        remaining_text = text[last_end:].strip()
        
        return complete_sentences, remaining_text
    
    def process_streaming_text(self, text_stream: Generator[str, None, None], 
                              tts_callback=None) -> Generator[str, None, None]:
        """处理流式文本，遇到完整句子就立即TTS"""
        buffer = ""
        sentence_count = 0
        
        print("🎵 开始流式TTS处理...")
        
        for chunk in text_stream:
            buffer += chunk
            yield chunk  # 继续传递原始流
            
            # 检查是否有完整句子
            if self.detect_sentence_end(buffer):
                complete_sentences, remaining = self.extract_complete_sentences(buffer)
                
                if complete_sentences:
                    sentence_count += 1
                    print(f"📢 检测到完整句子 #{sentence_count}: {complete_sentences}")
                    
                    # 立即开始TTS处理
                    if tts_callback:
                        threading.Thread(
                            target=tts_callback, 
                            args=(complete_sentences, sentence_count),
                            daemon=True
                        ).start()
                    
                    buffer = remaining
        
        # 处理最后的剩余文本
        if buffer.strip():
            sentence_count += 1
            print(f"📢 处理剩余文本 #{sentence_count}: {buffer}")
            if tts_callback:
                threading.Thread(
                    target=tts_callback, 
                    args=(buffer, sentence_count),
                    daemon=True
                ).start()

def mock_tts_synthesis(text: str, sentence_id: int):
    """模拟TTS合成过程"""
    print(f"🔊 开始合成句子 #{sentence_id}: {text}")
    # 模拟TTS处理时间
    time.sleep(0.5)  # 实际TTS可能需要更长时间
    print(f"✅ 完成合成句子 #{sentence_id}")

def simulate_ai_response_stream():
    """模拟AI回复的流式响应"""
    # 模拟一个典型的反诈回复
    full_response = "您好！我是中国联通反诈中心的AI专员。请问您最近有没有接到过可疑电话？对方有没有要求您提供验证码或者下载APP？如果有的话，千万不要相信！"
    
    # 模拟流式返回，每次返回几个字符
    for i in range(0, len(full_response), 3):
        chunk = full_response[i:i+3]
        yield chunk
        time.sleep(0.05)  # 模拟网络延迟

def demo_current_vs_streaming():
    """演示当前方式 vs 流式TTS的差异"""
    
    print("🔍 TTS流式优化演示")
    print("=" * 60)
    
    # 1. 当前方式：等待完整回复
    print("\n1️⃣ 当前方式：等待完整回复后TTS")
    start_time = time.time()
    
    full_text = ""
    for chunk in simulate_ai_response_stream():
        full_text += chunk
    
    print(f"📝 完整回复收到: {full_text}")
    mock_tts_synthesis(full_text, 1)
    
    current_total_time = time.time() - start_time
    print(f"⏱️ 当前方式总耗时: {current_total_time:.2f}秒")
    
    # 2. 流式方式：句子级别实时TTS
    print("\n2️⃣ 流式方式：句子级别实时TTS")
    start_time = time.time()
    
    processor = StreamingTTSProcessor()
    
    # 记录第一个句子的TTS开始时间
    first_tts_started = None
    
    def tts_with_timing(text: str, sentence_id: int):
        nonlocal first_tts_started
        if first_tts_started is None:
            first_tts_started = time.time()
            print(f"🎯 第一个句子TTS开始时间: {first_tts_started - start_time:.2f}秒")
        mock_tts_synthesis(text, sentence_id)
    
    # 处理流式文本
    for chunk in processor.process_streaming_text(
        simulate_ai_response_stream(), 
        tts_callback=tts_with_timing
    ):
        pass  # 在实际应用中，这里会继续处理chunk
    
    # 等待所有TTS完成
    time.sleep(1)
    
    streaming_total_time = time.time() - start_time
    print(f"⏱️ 流式方式总耗时: {streaming_total_time:.2f}秒")
    
    if first_tts_started:
        first_audio_delay = first_tts_started - start_time
        print(f"🎯 首次音频开始延迟: {first_audio_delay:.2f}秒")
        
        improvement = current_total_time - first_audio_delay
        print(f"🚀 预期改善: {improvement:.2f}秒 ({improvement/current_total_time*100:.1f}%)")

def main():
    """主演示函数"""
    print("🎵 TTS流式优化概念验证")
    print("=" * 60)
    print("目标：让WebSocket的首token优势转化为用户体验提升")
    print()
    
    demo_current_vs_streaming()
    
    print("\n" + "=" * 60)
    print("💡 关键洞察:")
    print("1. 当前TTS等待完整文本，抵消了WebSocket的优势")
    print("2. 句子级流式TTS可以让首token优势真正体现")
    print("3. 预期可减少200-500ms的首次音频播报延迟")
    print("4. 这将让WebSocket相比HTTP有明显的用户体验优势")

if __name__ == "__main__":
    main()
