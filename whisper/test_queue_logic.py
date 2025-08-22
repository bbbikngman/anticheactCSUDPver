#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试队列逻辑 - 验证生产者消费者模式
"""

import time
import queue
import threading
import re

def extract_complete_sentences(text: str) -> tuple:
    """提取所有完整句子和剩余文本"""
    sentence_endings = r'[。！？.!?]'
    
    # 找到所有句子结束位置
    end_positions = []
    for match in re.finditer(sentence_endings, text):
        end_positions.append(match.end())
    
    if not end_positions:
        return [], text
    
    # 提取所有完整句子
    sentences = []
    start = 0
    for end_pos in end_positions:
        sentence = text[start:end_pos].strip()
        if sentence:
            sentences.append(sentence)
        start = end_pos
    
    # 剩余文本
    remaining = text[start:].strip() if start < len(text) else ""
    
    return sentences, remaining

class MockTTSModule:
    """模拟TTS模块"""
    
    def __init__(self):
        self.is_playing = False
        self.current_text = ""
        self.play_thread = None
    
    def speak_async(self, text, speaker_wav=None):
        """异步播放文本"""
        def async_play():
            self.current_text = text
            self.is_playing = True
            print(f"🔊 [TTS] 开始播放: '{text}'")
            
            # 模拟播放时间（根据文本长度）
            play_time = len(text) * 0.05  # 每个字符0.05秒
            time.sleep(play_time)
            
            self.is_playing = False
            print(f"✅ [TTS] 播放完成: '{text}'")
        
        self.play_thread = threading.Thread(target=async_play, daemon=True)
        self.play_thread.start()
        return self.play_thread

class StreamingTTSProcessor:
    """流式TTS处理器 - 生产者消费者模式"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
        self.audio_queue = queue.Queue()
        self.is_processing = False
        self.consumer_thread = None
        
    def start_consumer(self):
        """启动音频消费者线程"""
        if not self.is_processing:
            self.is_processing = True
            self.consumer_thread = threading.Thread(target=self._audio_consumer, daemon=True)
            self.consumer_thread.start()
            print("🎵 音频消费者线程已启动")
    
    def stop_consumer(self):
        """停止音频消费者"""
        self.is_processing = False
        self.audio_queue.put(None)  # 发送停止信号
        if self.consumer_thread:
            self.consumer_thread.join(timeout=1)
        print("🎵 音频消费者线程已停止")
    
    def _audio_consumer(self):
        """音频消费者 - 连续播放音频队列中的内容"""
        print("🔊 音频消费者开始工作...")
        
        while self.is_processing:
            try:
                audio_item = self.audio_queue.get(timeout=0.5)
                
                if audio_item is None:  # 停止信号
                    break
                
                sentence, sentence_id = audio_item
                print(f"🎵 准备播放句子 #{sentence_id}: '{sentence}'")
                
                # 确保前一个音频播放完成
                while self.tts_module.is_playing:
                    print(f"⏳ 等待前一个音频播放完成...")
                    time.sleep(0.1)
                
                # 开始播放当前句子（异步）
                play_start_time = time.time()
                play_thread = self.tts_module.speak_async(sentence, speaker_wav=self.speaker_wav)
                
                # 等待当前音频开始播放
                wait_count = 0
                while not self.tts_module.is_playing and wait_count < 50:
                    time.sleep(0.01)
                    wait_count += 1
                
                if self.tts_module.is_playing:
                    actual_start_time = time.time() - play_start_time
                    print(f"🔊 句子 #{sentence_id} 开始播放 (启动耗时: {actual_start_time:.3f}s)")
                else:
                    print(f"⚠️ 句子 #{sentence_id} 播放启动失败")
                
                # 不等待播放完成，立即处理下一个句子
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 音频播放错误: {e}")
        
        # 等待最后一个音频播放完成
        if self.tts_module.is_playing:
            print("⏳ 等待最后一个音频播放完成...")
            while self.tts_module.is_playing:
                time.sleep(0.1)
        
        print("🔊 音频消费者结束工作")
    
    def add_sentence(self, sentence: str, sentence_id: int):
        """添加句子到播放队列"""
        if sentence.strip():
            self.audio_queue.put((sentence, sentence_id))
            print(f"📝 句子 #{sentence_id} 已加入播放队列")
    
    def process_streaming_response(self, response_chunks, ai_start_time):
        """处理流式响应 - 生产者"""
        print("🤖 开始流式响应处理...")
        
        buffer = ""
        sentence_count = 0
        first_token_received = False
        
        for chunk in response_chunks:
            current_time = time.time()
            
            # 记录首token时间
            if not first_token_received:
                first_token_delay = current_time - ai_start_time
                print(f"⚡ 首token延迟: {first_token_delay:.3f}s")
                first_token_received = True
            
            buffer += chunk
            print(f"📥 收到chunk: '{chunk}' (buffer: '{buffer}')")
            
            # 检查是否有完整句子
            sentences, remaining = extract_complete_sentences(buffer)
            
            if sentences:
                # 处理所有完整句子
                for sentence in sentences:
                    sentence_count += 1
                    sentence_delay = current_time - ai_start_time
                    print(f"🎯 句子 #{sentence_count} 检测 ({sentence_delay:.3f}s): '{sentence}'")
                    
                    # 立即加入播放队列
                    self.add_sentence(sentence, sentence_count)
                
                # 更新buffer为剩余文本
                buffer = remaining
            
            # 模拟网络延迟
            time.sleep(0.05)
        
        # 处理最后的剩余文本
        if buffer.strip():
            sentence_count += 1
            print(f"🎯 最后片段 #{sentence_count}: '{buffer}'")
            self.add_sentence(buffer, sentence_count)
        
        response_complete_time = time.time()
        total_delay = response_complete_time - ai_start_time
        print(f"📄 AI回复完成: {total_delay:.3f}s，共生成 {sentence_count} 个音频片段")

def test_streaming_tts():
    """测试流式TTS处理"""
    print("🧪 测试流式TTS处理...")
    
    # 模拟AI流式回复
    mock_response = [
        "您", "先", "别", "急", "，", "这", "个", "验", "证", "码", "是", "要", "发", "给", "您", "的", 
        "银", "行", "卡", "还", "是", "手", "机", "号", "的", "？", "千", "万", "不", "要", "给", "陌", "生", "人", "！",
        "如", "果", "您", "已", "经", "提", "供", "了", "，", "请", "立", "即", "联", "系", "银", "行", "。"
    ]
    
    # 创建模拟TTS和处理器
    mock_tts = MockTTSModule()
    processor = StreamingTTSProcessor(mock_tts)
    
    # 启动消费者
    processor.start_consumer()
    
    try:
        # 开始处理
        start_time = time.time()
        print(f"🚀 开始时间: {start_time}")
        
        # 在单独线程中运行生产者
        def run_producer():
            processor.process_streaming_response(mock_response, start_time)
        
        producer_thread = threading.Thread(target=run_producer, daemon=True)
        producer_thread.start()
        
        # 等待生产者完成
        producer_thread.join()
        
        # 等待所有音频播放完成
        print("⏳ 等待所有音频播放完成...")
        time.sleep(3)  # 给足够时间让队列处理完
        
    finally:
        # 停止消费者
        processor.stop_consumer()
    
    total_time = time.time() - start_time
    print(f"🎯 总测试时间: {total_time:.3f}s")

def main():
    """主测试函数"""
    print("🧪 队列逻辑测试")
    print("=" * 50)
    
    test_streaming_tts()
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 预期效果:")
    print("1. 🎯 第一句话检测到立即加入队列")
    print("2. 🔊 第一句话立即开始播放")
    print("3. 📝 第二句话检测到加入队列")
    print("4. ⏳ 第二句话等待第一句播放完成后立即播放")
    print("5. 🔄 生产和消费并行进行")

if __name__ == "__main__":
    main()
