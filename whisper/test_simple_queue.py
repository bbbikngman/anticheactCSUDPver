#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简单队列架构
"""

import time
import queue
import threading
import re

def extract_playable_segments(text: str) -> tuple:
    """提取可播放的语音片段（包括逗号分割）"""
    segment_endings = r'[，。！？,;；.!?]'
    
    end_positions = []
    for match in re.finditer(segment_endings, text):
        end_positions.append(match.end())
    
    if not end_positions:
        return [], text
    
    segments = []
    start = 0
    for end_pos in end_positions:
        segment = text[start:end_pos].strip()
        if segment and len(segment) > 2:
            segments.append(segment)
        start = end_pos
    
    remaining = text[start:].strip() if start < len(text) else ""
    return segments, remaining

class MockTTSModule:
    """模拟TTS模块"""
    
    def __init__(self):
        self.is_playing = False
        self.current_text = ""
    
    def speak(self, text, speaker_wav=None):
        """模拟语音合成"""
        self.current_text = text
        self.is_playing = True
        print(f"🔊 [TTS] 开始播放: '{text}'")
        
        # 模拟播放时间
        play_time = len(text) * 0.08
        time.sleep(play_time)
        
        self.is_playing = False
        print(f"✅ [TTS] 播放完成: '{text}'")

class SimpleStreamingTTS:
    """简单的流式TTS - 正确的生产者消费者模式"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
        self.text_queue = queue.Queue()  # 文本队列
        self.is_running = False
        self.consumer_thread = None
        
    def start(self):
        """启动消费者"""
        if not self.is_running:
            self.is_running = True
            self.consumer_thread = threading.Thread(target=self._consumer, daemon=True)
            self.consumer_thread.start()
            print("🎵 TTS消费者已启动")
    
    def stop(self):
        """停止消费者"""
        self.is_running = False
        self.text_queue.put(None)  # 停止信号
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2)
        print("🎵 TTS消费者已停止")
    
    def _consumer(self):
        """消费者线程 - 循环处理TTS任务"""
        print("🔊 TTS消费者开始工作...")
        
        while self.is_running:
            try:
                item = self.text_queue.get(timeout=0.5)
                
                if item is None:  # 停止信号
                    break
                
                text, segment_id = item
                print(f"🔊 开始播放片段 #{segment_id}: '{text}'")
                
                # 直接播放，阻塞直到完成
                self.tts_module.speak(text, speaker_wav=self.speaker_wav)
                print(f"✅ 片段 #{segment_id} 播放完成")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ TTS播放错误: {e}")
        
        print("🔊 TTS消费者结束工作")
    
    def add_text(self, text: str, segment_id: int):
        """添加文本到播放队列"""
        if text.strip():
            self.text_queue.put((text, segment_id))
            print(f"📝 片段 #{segment_id} 已加入TTS队列: '{text}'")

def process_streaming_with_queue(tts_queue, response_chunks, ai_start_time):
    """使用队列的流式处理 - 正确的生产者"""
    print("🤖 开始流式响应处理...")
    
    buffer = ""
    first_token_received = False
    segment_count = 0
    
    for chunk in response_chunks:
        current_time = time.time()
        
        # 记录首token时间
        if not first_token_received:
            first_token_delay = current_time - ai_start_time
            print(f"⚡ 首token延迟: {first_token_delay:.3f}s")
            first_token_received = True
        
        buffer += chunk
        print(f"📥 收到chunk: '{chunk}' (buffer: '{buffer}')")
        
        # 检查是否有新的可播放片段
        segments, remaining = extract_playable_segments(buffer)
        
        # 处理新检测到的片段
        if segments:
            for segment in segments:
                segment_count += 1
                segment_delay = current_time - ai_start_time
                print(f"🎯 片段 #{segment_count} 检测 ({segment_delay:.3f}s): '{segment}'")
                
                # 立即加入TTS队列
                tts_queue.add_text(segment, segment_count)
            
            # 更新buffer为剩余文本
            buffer = remaining
        
        # 模拟网络延迟
        time.sleep(0.05)
    
    # 处理最后的剩余文本
    if buffer.strip() and len(buffer.strip()) > 2:
        segment_count += 1
        print(f"🎯 最后片段 #{segment_count}: '{buffer}'")
        tts_queue.add_text(buffer, segment_count)
    
    response_complete_time = time.time()
    total_delay = response_complete_time - ai_start_time
    print(f"📄 AI回复完成: {total_delay:.3f}s，共生成 {segment_count} 个片段")

def test_simple_queue_architecture():
    """测试简单队列架构"""
    print("🧪 测试简单队列架构...")
    
    # 模拟AI流式回复
    mock_response = [
        "好", "的", "，", "您", "认", "识", "对", "方", "，", "那", "能", "说", "说", 
        "大", "概", "是", "什", "么", "事", "吗", "？"
    ]
    
    # 创建模拟TTS和队列
    mock_tts = MockTTSModule()
    tts_queue = SimpleStreamingTTS(mock_tts)
    
    # 启动消费者
    tts_queue.start()
    
    try:
        # 开始处理
        start_time = time.time()
        process_streaming_with_queue(tts_queue, mock_response, start_time)
        
        # 等待所有播放完成
        print("⏳ 等待所有播放完成...")
        time.sleep(3)
        
    finally:
        # 停止消费者
        tts_queue.stop()
    
    total_time = time.time() - start_time
    print(f"🎯 总测试时间: {total_time:.3f}s")

def main():
    """主测试函数"""
    print("🧪 简单队列架构测试")
    print("=" * 50)
    
    test_simple_queue_architecture()
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 正确的架构:")
    print("1. 🎯 检测到标点符号 → 立即加入TTS队列")
    print("2. 🔊 TTS消费者循环 → 有任务就播放")
    print("3. ✅ 播放完成 → 立即处理下一个")
    print("4. 🚀 简单、可靠、无重复播放")

if __name__ == "__main__":
    main()
