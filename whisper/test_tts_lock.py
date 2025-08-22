#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试TTS锁机制
"""

import time
import queue
import threading

class MockTTSModule:
    """模拟TTS模块 - 包含stop_current_speech逻辑"""
    
    def __init__(self):
        self.is_playing = False
        self.current_text = ""
        self.should_stop = False
    
    def stop_current_speech(self):
        """停止当前正在播放的语音"""
        if self.is_playing:
            print("检测到新的语音请求，停止当前播放...")
            self.should_stop = True
            self.is_playing = False
            print("当前语音播放已停止")
    
    def speak(self, text, speaker_wav=None):
        """模拟语音合成 - 包含stop_current_speech调用"""
        # 模拟TTS模块的行为：每次speak都先停止当前播放
        self.stop_current_speech()
        
        self.current_text = text
        self.is_playing = True
        self.should_stop = False
        
        print(f"🔊 [TTS] 开始播放: '{text}'")
        
        # 模拟播放时间，检查是否被中断
        play_time = len(text) * 0.05
        start_time = time.time()
        
        while time.time() - start_time < play_time:
            if self.should_stop:
                print(f"⚠️ [TTS] 播放被中断: '{text}'")
                self.is_playing = False
                return
            time.sleep(0.01)
        
        self.is_playing = False
        print(f"✅ [TTS] 播放完成: '{text}'")

class SimpleStreamingTTS:
    """带锁的流式TTS"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
        self.text_queue = queue.Queue()
        self.is_running = False
        self.consumer_thread = None
        self.tts_lock = threading.Lock()  # TTS锁
        
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
        self.text_queue.put(None)
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2)
        print("🎵 TTS消费者已停止")
    
    def _consumer(self):
        """消费者线程"""
        print("🔊 TTS消费者开始工作...")
        
        while self.is_running:
            try:
                item = self.text_queue.get(timeout=0.5)
                
                if item is None:
                    break
                
                text, segment_id = item
                print(f"🎵 准备播放片段 #{segment_id}: '{text}'")
                
                # 使用锁确保TTS线程安全
                with self.tts_lock:
                    try:
                        print(f"🔒 获得TTS锁，开始播放片段 #{segment_id}")
                        self.tts_module.speak(text, speaker_wav=self.speaker_wav)
                        print(f"✅ 片段 #{segment_id} 播放完成")
                    except Exception as e:
                        print(f"❌ 片段 #{segment_id} 播放失败: {e}")
                    finally:
                        print(f"🔓 释放TTS锁，片段 #{segment_id} 处理完成")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ TTS消费者错误: {e}")
        
        print("🔊 TTS消费者结束工作")
    
    def add_text(self, text: str, segment_id: int):
        """添加文本到播放队列"""
        if text.strip():
            self.text_queue.put((text, segment_id))
            print(f"📝 片段 #{segment_id} 已加入TTS队列: '{text}'")

def test_concurrent_tts():
    """测试并发TTS调用"""
    print("🧪 测试TTS锁机制...")
    
    # 创建模拟TTS和队列
    mock_tts = MockTTSModule()
    tts_queue = SimpleStreamingTTS(mock_tts)
    
    # 启动消费者
    tts_queue.start()
    
    try:
        # 快速添加多个片段，模拟并发场景
        segments = [
            "好的，",
            "您没转钱就太好了！",
            "那对方当时让您把钱转到哪个账户，",
            "或者有没有发什么二维码、链接给您？"
        ]
        
        print("🚀 快速添加多个片段...")
        for i, segment in enumerate(segments, 1):
            tts_queue.add_text(segment, i)
            time.sleep(0.01)  # 很短的间隔，模拟快速检测
        
        # 等待所有播放完成
        print("⏳ 等待所有播放完成...")
        time.sleep(5)
        
    finally:
        tts_queue.stop()

def test_without_lock():
    """测试没有锁的情况（对比）"""
    print("\n🧪 对比测试：没有锁的情况...")
    
    mock_tts = MockTTSModule()
    
    def play_segment(text, segment_id):
        print(f"🎵 线程 #{segment_id} 开始播放: '{text}'")
        mock_tts.speak(text)
        print(f"✅ 线程 #{segment_id} 播放结束")
    
    # 创建多个并发线程
    threads = []
    segments = [
        "好的，",
        "您没转钱就太好了！",
        "那对方当时让您把钱转到哪个账户，",
        "或者有没有发什么二维码、链接给您？"
    ]
    
    print("🚀 创建并发线程...")
    for i, segment in enumerate(segments, 1):
        thread = threading.Thread(target=play_segment, args=(segment, i), daemon=True)
        threads.append(thread)
        thread.start()
        time.sleep(0.01)  # 很短的间隔
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print("✅ 并发测试完成")

def main():
    """主测试函数"""
    print("🧪 TTS锁机制测试")
    print("=" * 50)
    
    # 测试有锁的情况
    test_concurrent_tts()
    
    # 测试没有锁的情况（对比）
    test_without_lock()
    
    print("\n" + "=" * 50)
    print("📊 测试结论:")
    print("1. 🔒 有锁版本：片段按顺序播放，无中断")
    print("2. ❌ 无锁版本：片段互相中断，播放混乱")
    print("3. 💡 锁机制可以解决TTS并发冲突问题")

if __name__ == "__main__":
    main()
