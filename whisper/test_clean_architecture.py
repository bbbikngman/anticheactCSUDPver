#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试全新的干净架构
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
    """模拟TTS模块 - 简化版本"""
    
    def __init__(self):
        self.is_playing = False
    
    def _synthesize_with_edge_tts(self, text):
        """模拟Edge TTS"""
        print(f"🔊 [Edge TTS] 播放: '{text}'")
        play_time = len(text) * 0.05
        time.sleep(play_time)
        print(f"✅ [Edge TTS] 完成: '{text}'")
    
    def speak(self, text, speaker_wav=None):
        """备用方法"""
        print(f"🔊 [Backup TTS] 播放: '{text}'")
        play_time = len(text) * 0.05
        time.sleep(play_time)
        print(f"✅ [Backup TTS] 完成: '{text}'")

class CleanStreamingTTS:
    """全新的干净TTS队列实现"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
    def start(self):
        """启动工作线程"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            print("🎵 TTS工作线程已启动")
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False
        self.audio_queue.put(("STOP", 0))
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3)
        print("🎵 TTS工作线程已停止")
    
    def _worker(self):
        """工作线程 - 独立的TTS播放器"""
        print("🔊 TTS工作线程开始...")
        
        while self.is_running:
            try:
                item = self.audio_queue.get(timeout=1.0)
                
                if item[0] == "STOP":
                    break
                
                text, segment_id = item
                print(f"🎵 播放片段 #{segment_id}: '{text}'")
                
                # 创建独立的TTS实例避免冲突
                try:
                    # 直接调用TTS，完全阻塞
                    self._safe_tts_call(text)
                    print(f"✅ 片段 #{segment_id} 播放完成")
                except Exception as e:
                    print(f"❌ 片段 #{segment_id} 播放失败: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ TTS工作线程错误: {e}")
        
        print("🔊 TTS工作线程结束")
    
    def _safe_tts_call(self, text):
        """安全的TTS调用 - 避免并发问题"""
        # 使用最简单的方式：直接调用TTS的底层方法
        try:
            if hasattr(self.tts_module, '_synthesize_with_edge_tts'):
                print(f"🔊 使用Edge TTS播放: '{text}'")
                self.tts_module._synthesize_with_edge_tts(text)
            elif hasattr(self.tts_module, '_fallback_tts_interruptible'):
                print(f"🔊 使用备用TTS播放: '{text}'")
                self.tts_module._fallback_tts_interruptible(text)
            else:
                # 最后的备选方案
                print(f"🔊 使用标准TTS播放: '{text}'")
                self.tts_module.speak(text, speaker_wav=self.speaker_wav)
        except Exception as e:
            print(f"❌ TTS调用失败: {e}")
            raise
    
    def add_audio(self, text: str, segment_id: int):
        """添加音频到播放队列"""
        if text.strip():
            self.audio_queue.put((text, segment_id))
            print(f"📝 片段 #{segment_id} 已加入音频队列: '{text}'")

def clean_streaming_producer(audio_queue, response_chunks, ai_start_time):
    """干净的流式生产者 - 完全独立"""
    print("🤖 生产者开始处理AI响应...")
    
    buffer = ""
    first_token_received = False
    segment_count = 0
    
    try:
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
                    
                    # 立即加入音频队列
                    audio_queue.add_audio(segment, segment_count)
                
                # 更新buffer为剩余文本
                buffer = remaining
            
            # 模拟网络延迟
            time.sleep(0.05)
        
        # 处理最后的剩余文本
        if buffer.strip() and len(buffer.strip()) > 2:
            segment_count += 1
            print(f"🎯 最后片段 #{segment_count}: '{buffer}'")
            audio_queue.add_audio(buffer, segment_count)
        
        response_complete_time = time.time()
        total_delay = response_complete_time - ai_start_time
        print(f"📄 生产者完成: {total_delay:.3f}s，共生成 {segment_count} 个片段")
        
    except Exception as e:
        print(f"❌ 生产者错误: {e}")
        import traceback
        traceback.print_exc()

def test_clean_architecture():
    """测试干净架构"""
    print("🧪 测试全新的干净架构...")
    
    # 模拟AI流式回复
    mock_response = [
        "好", "的", "，", "您", "没", "转", "钱", "就", "太", "好", "了", "！",
        "那", "对", "方", "当", "时", "让", "您", "把", "钱", "转", "到", "哪", "个", "账", "户", "，",
        "或", "者", "有", "没", "有", "发", "什", "么", "二", "维", "码", "、", "链", "接", "给", "您", "？"
    ]
    
    # 创建模拟TTS和队列
    mock_tts = MockTTSModule()
    audio_queue = CleanStreamingTTS(mock_tts)
    
    # 启动消费者
    audio_queue.start()
    
    try:
        # 在独立线程中运行生产者
        start_time = time.time()
        
        def run_producer():
            clean_streaming_producer(audio_queue, mock_response, start_time)
        
        producer_thread = threading.Thread(target=run_producer, daemon=True)
        producer_thread.start()
        
        # 等待生产者完成
        producer_thread.join()
        
        # 等待音频播放完成
        print("⏳ 等待音频播放完成...")
        time.sleep(3)
        
    finally:
        # 停止消费者
        audio_queue.stop()
    
    total_time = time.time() - start_time
    print(f"🎯 总测试时间: {total_time:.3f}s")

def main():
    """主测试函数"""
    print("🧪 全新干净架构测试")
    print("=" * 50)
    
    test_clean_architecture()
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 全新架构特点:")
    print("1. 🔄 生产者和消费者完全独立")
    print("2. 🔊 直接调用TTS底层方法，避免冲突")
    print("3. 🎵 独立工作线程，无并发问题")
    print("4. 🚀 简单、可靠、无重复播放")

if __name__ == "__main__":
    main()
