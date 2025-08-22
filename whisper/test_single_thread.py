#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单线程消费
"""

import time
import queue
import threading

class MockTTSModule:
    """模拟TTS模块 - 记录线程信息"""
    
    def __init__(self):
        self.call_count = 0
        self.thread_ids = []
    
    def speak(self, text, speaker_wav=None):
        """记录调用的线程ID"""
        current_thread = threading.current_thread()
        self.call_count += 1
        self.thread_ids.append(current_thread.ident)
        
        print(f"🔊 [TTS] 线程 {current_thread.ident} 播放: '{text}'")
        
        # 模拟播放时间
        play_time = len(text) * 0.03
        time.sleep(play_time)
        
        print(f"✅ [TTS] 线程 {current_thread.ident} 完成: '{text}'")

class CleanStreamingTTS:
    """单线程消费的TTS队列"""
    
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
            print(f"🎵 TTS工作线程已启动 (线程ID: {self.worker_thread.ident})")
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False
        self.audio_queue.put(("STOP", 0))
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3)
        print("🎵 TTS工作线程已停止")
    
    def _worker(self):
        """工作线程 - 单线程消费者"""
        current_thread = threading.current_thread()
        print(f"🔊 TTS工作线程开始... (线程ID: {current_thread.ident})")
        
        while self.is_running:
            try:
                item = self.audio_queue.get(timeout=1.0)
                
                if item[0] == "STOP":
                    break
                
                text, segment_id = item
                print(f"🎵 播放片段 #{segment_id}: '{text}' (线程ID: {current_thread.ident})")
                
                # 直接调用TTS，确保在同一线程中
                try:
                    self._safe_tts_call(text)
                    print(f"✅ 片段 #{segment_id} 播放完成")
                except Exception as e:
                    print(f"❌ 片段 #{segment_id} 播放失败: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ TTS工作线程错误: {e}")
        
        print(f"🔊 TTS工作线程结束 (线程ID: {current_thread.ident})")
    
    def _safe_tts_call(self, text):
        """安全的TTS调用 - 确保单线程"""
        current_thread = threading.current_thread()
        print(f"🔊 单线程TTS播放: '{text}' (线程ID: {current_thread.ident})")
        
        # 直接调用speak方法
        self.tts_module.speak(text, speaker_wav=self.speaker_wav)
        
        print(f"✅ 单线程TTS完成: '{text}' (线程ID: {current_thread.ident})")
    
    def add_audio(self, text: str, segment_id: int):
        """添加音频到播放队列"""
        if text.strip():
            self.audio_queue.put((text, segment_id))
            print(f"📝 片段 #{segment_id} 已加入音频队列: '{text}'")

def test_single_thread_consumption():
    """测试单线程消费"""
    print("🧪 测试单线程消费...")
    
    # 创建模拟TTS和队列
    mock_tts = MockTTSModule()
    audio_queue = CleanStreamingTTS(mock_tts)
    
    # 启动消费者
    audio_queue.start()
    
    try:
        # 快速添加多个片段
        segments = [
            "您好，",
            "我在呢！",
            "刚刚说到那个0044-9811的号码，",
            "您这边还有印象吗？"
        ]
        
        print("🚀 快速添加多个片段...")
        for i, segment in enumerate(segments, 1):
            audio_queue.add_audio(segment, i)
            time.sleep(0.01)  # 很短的间隔
        
        # 等待所有播放完成
        print("⏳ 等待所有播放完成...")
        time.sleep(3)
        
    finally:
        audio_queue.stop()
    
    # 分析线程使用情况
    print(f"\n📊 线程使用分析:")
    print(f"TTS调用总次数: {mock_tts.call_count}")
    print(f"使用的线程ID: {set(mock_tts.thread_ids)}")
    
    if len(set(mock_tts.thread_ids)) == 1:
        print("✅ 完美！所有TTS调用都在同一个线程中")
        return True
    else:
        print("❌ 错误！TTS调用使用了多个线程")
        print(f"线程ID列表: {mock_tts.thread_ids}")
        return False

def test_main_thread_info():
    """显示主线程信息"""
    main_thread = threading.current_thread()
    print(f"🧵 主线程ID: {main_thread.ident}")
    print(f"🧵 主线程名称: {main_thread.name}")

def main():
    """主测试函数"""
    print("🧪 单线程消费测试")
    print("=" * 50)
    
    # 显示主线程信息
    test_main_thread_info()
    
    # 测试单线程消费
    success = test_single_thread_consumption()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 单线程消费测试通过！")
        print("\n💡 关键特点:")
        print("1. 🔄 只有一个TTS工作线程")
        print("2. 🎵 所有TTS调用都在同一线程中")
        print("3. 🚀 无线程竞争，播放顺序正确")
        print("4. 📝 队列确保线性消费")
    else:
        print("❌ 单线程消费测试失败！")
        print("需要检查TTS模块是否创建了额外的线程")

if __name__ == "__main__":
    main()
