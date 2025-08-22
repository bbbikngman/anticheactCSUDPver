#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完全同步的TTS调用
"""

import time
import queue
import threading

class MockTTSModule:
    """模拟TTS模块 - 包含Edge TTS"""
    
    def __init__(self):
        self.call_count = 0
        self.thread_ids = []
        self.edge_tts = MockEdgeTTS()
        self.should_stop = False
        self.is_playing = False
    
    def speak(self, text, speaker_wav=None):
        """模拟speak方法 - 会调用stop_current_speech"""
        current_thread = threading.current_thread()
        self.call_count += 1
        self.thread_ids.append(current_thread.ident)
        
        # 模拟TTS模块的问题行为
        self.stop_current_speech()
        
        print(f"🔊 [TTS.speak] 线程 {current_thread.ident} 播放: '{text}'")
        time.sleep(len(text) * 0.02)
        print(f"✅ [TTS.speak] 线程 {current_thread.ident} 完成: '{text}'")
    
    def stop_current_speech(self):
        """模拟停止当前播放"""
        if self.is_playing:
            print("检测到新的语音请求，停止当前播放...")
            self.should_stop = True
            self.is_playing = False
            print("当前语音播放已停止")
    
    def _play_audio_bytes(self, audio_bytes, text):
        """模拟播放音频字节"""
        current_thread = threading.current_thread()
        print(f"🔊 [播放音频] 线程 {current_thread.ident}: '{text}'")
        time.sleep(len(text) * 0.02)
        print(f"✅ [播放音频] 线程 {current_thread.ident} 完成: '{text}'")

class MockEdgeTTS:
    """模拟Edge TTS"""
    
    def Communicate(self, text, voice, rate=None, volume=None):
        return MockCommunicate(text)

class MockCommunicate:
    """模拟Communicate对象"""
    
    def __init__(self, text):
        self.text = text
    
    async def stream(self):
        """模拟流式返回"""
        # 模拟音频数据
        yield {"type": "audio", "data": self.text.encode()}

class CleanStreamingTTS:
    """带同步TTS的队列"""
    
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
        """工作线程"""
        current_thread = threading.current_thread()
        print(f"🔊 TTS工作线程开始... (线程ID: {current_thread.ident})")
        
        while self.is_running:
            try:
                item = self.audio_queue.get(timeout=1.0)
                
                if item[0] == "STOP":
                    break
                
                text, segment_id = item
                print(f"🎵 播放片段 #{segment_id}: '{text}' (线程ID: {current_thread.ident})")
                
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
        """完全同步的TTS调用"""
        try:
            print(f"🔊 同步TTS播放: '{text}'")
            
            # 方案1：尝试直接调用同步版本的Edge TTS
            if hasattr(self.tts_module, 'edge_tts') and self.tts_module.edge_tts:
                self._sync_edge_tts_call(text)
            else:
                # 方案2：使用备用TTS
                print(f"🔊 使用备用TTS: '{text}'")
                self.tts_module.speak(text, speaker_wav=self.speaker_wav)
            
            print(f"✅ 同步TTS完成: '{text}'")
            
        except Exception as e:
            print(f"❌ TTS调用失败: {e}")
            raise
    
    def _sync_edge_tts_call(self, text):
        """完全同步的Edge TTS调用"""
        try:
            import asyncio
            
            print(f"🔊 同步Edge TTS: '{text}'")
            
            async def synthesize():
                communicate = self.tts_module.edge_tts.Communicate(
                    text, "zh-CN-XiaoxiaoNeural"
                )
                audio_data = b""

                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]

                return audio_data

            # 同步运行异步函数
            audio_bytes = asyncio.run(synthesize())
            
            if audio_bytes:
                # 直接播放音频，不创建新线程
                self.tts_module._play_audio_bytes(audio_bytes, text)
            
        except Exception as e:
            print(f"❌ 同步Edge TTS失败: {e}")
            raise
    
    def add_audio(self, text: str, segment_id: int):
        """添加音频到播放队列"""
        if text.strip():
            self.audio_queue.put((text, segment_id))
            print(f"📝 片段 #{segment_id} 已加入音频队列: '{text}'")

def test_sync_tts():
    """测试同步TTS"""
    print("🧪 测试完全同步的TTS调用...")
    
    # 创建模拟TTS和队列
    mock_tts = MockTTSModule()
    audio_queue = CleanStreamingTTS(mock_tts)
    
    # 启动消费者
    audio_queue.start()
    
    try:
        # 快速添加多个片段
        segments = [
            "好的，",
            "您挂断得很及时，",
            "做得对！",
            "这类00853开头的境外陌生号八成是诈骗，"
        ]
        
        print("🚀 快速添加多个片段...")
        for i, segment in enumerate(segments, 1):
            audio_queue.add_audio(segment, i)
            time.sleep(0.01)
        
        # 等待所有播放完成
        print("⏳ 等待所有播放完成...")
        time.sleep(3)
        
    finally:
        audio_queue.stop()
    
    # 检查是否有"停止当前播放"的消息
    print(f"\n📊 测试结果分析:")
    print(f"如果没有看到'检测到新的语音请求，停止当前播放'消息，")
    print(f"说明同步TTS调用成功避免了冲突！")

def main():
    """主测试函数"""
    print("🧪 同步TTS测试")
    print("=" * 50)
    
    test_sync_tts()
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 同步TTS的优势:")
    print("1. 🔄 完全在单线程中执行")
    print("2. 🚫 不会触发stop_current_speech")
    print("3. 🎵 无线程竞争，播放顺序正确")
    print("4. 🔊 直接调用底层播放方法")

if __name__ == "__main__":
    main()
