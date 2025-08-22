#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试顺序播放逻辑
"""

import time
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

class StreamingTTSProcessor:
    """流式TTS处理器"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
    
    def process_streaming_response_simple(self, response_chunks, ai_start_time):
        """简化的流式响应处理 - 顺序播放所有片段"""
        print("🤖 开始流式响应处理...")
        
        buffer = ""
        first_token_received = False
        played_segments = []
        
        for chunk in response_chunks:
            current_time = time.time()
            
            # 记录首token时间
            if not first_token_received:
                first_token_delay = current_time - ai_start_time
                print(f"⚡ 首token延迟: {first_token_delay:.3f}s")
                first_token_received = True
            
            buffer += chunk
            
            # 检查所有可播放片段
            segments, remaining = extract_playable_segments(buffer)
            
            # 找出新增的片段（相比已播放的）
            if len(segments) > len(played_segments):
                new_segments = segments[len(played_segments):]
                
                # 只播放第一个新片段，其他的加入队列
                first_new_segment = new_segments[0]
                segment_count = len(played_segments) + 1
                segment_delay = current_time - ai_start_time
                print(f"🎯 片段 #{segment_count} 检测 ({segment_delay:.3f}s): '{first_new_segment}'")
                
                # 如果是第一个片段，立即播放
                if len(played_segments) == 0:
                    print(f"🔊 开始播放片段 #{segment_count}: '{first_new_segment}'")
                    
                    def play_first_segment():
                        self.tts_module.speak(first_new_segment, speaker_wav=self.speaker_wav)
                    
                    audio_thread = threading.Thread(target=play_first_segment, daemon=True)
                    audio_thread.start()
                    
                    # 等待音频开始播放
                    wait_count = 0
                    while not self.tts_module.is_playing and wait_count < 50:
                        time.sleep(0.01)
                        wait_count += 1
                    
                    if self.tts_module.is_playing:
                        audio_delay = time.time() - ai_start_time
                        print(f"🎵 音频播放开始: {audio_delay:.3f}s")
                
                # 记录所有新片段
                for segment in new_segments:
                    played_segments.append(segment)
                    if segment != first_new_segment:
                        print(f"📝 片段 #{len(played_segments)} 已记录: '{segment}'")
            
            # 模拟网络延迟
            time.sleep(0.05)
        
        response_complete_time = time.time()
        total_delay = response_complete_time - ai_start_time
        print(f"📄 AI回复完成: {total_delay:.3f}s，共生成 {len(played_segments)} 个音频片段")
        
        # 播放剩余片段
        if len(played_segments) > 1:
            def play_remaining_segments():
                # 等待第一个片段播放完成
                while self.tts_module.is_playing:
                    time.sleep(0.1)
                
                # 播放剩余片段
                for i, segment in enumerate(played_segments[1:], 2):
                    print(f"🔊 开始播放片段 #{i}: '{segment}'")
                    self.tts_module.speak(segment, speaker_wav=self.speaker_wav)
                    
                    # 等待当前片段播放完成
                    while self.tts_module.is_playing:
                        time.sleep(0.1)
                    
                    print(f"✅ 片段 #{i} 播放完成")
            
            remaining_thread = threading.Thread(target=play_remaining_segments, daemon=True)
            remaining_thread.start()
            
            # 等待所有播放完成
            remaining_thread.join()
        
        return len(played_segments)

def test_sequential_playback():
    """测试顺序播放"""
    print("🧪 测试顺序播放...")
    
    # 模拟AI流式回复
    mock_response = [
        "好", "的", "，", "您", "认", "识", "对", "方", "，", "那", "能", "说", "说", 
        "大", "概", "是", "什", "么", "事", "吗", "？"
    ]
    
    # 创建模拟TTS和处理器
    mock_tts = MockTTSModule()
    processor = StreamingTTSProcessor(mock_tts)
    
    # 开始处理
    start_time = time.time()
    segment_count = processor.process_streaming_response_simple(mock_response, start_time)
    
    total_time = time.time() - start_time
    print(f"🎯 总测试时间: {total_time:.3f}s")
    print(f"📊 播放片段数: {segment_count}")
    
    return segment_count

def main():
    """主测试函数"""
    print("🧪 顺序播放测试")
    print("=" * 50)
    
    segment_count = test_sequential_playback()
    
    print("\n" + "=" * 50)
    print("📊 测试结果:")
    
    if segment_count >= 3:
        print("✅ 顺序播放测试通过！")
        print(f"🎯 成功播放 {segment_count} 个片段")
        print("\n💡 预期播放顺序:")
        print("1. 🎵 '好的，' - 立即播放")
        print("2. 🎵 '您认识对方，' - 第一个播放完后立即播放")
        print("3. 🎵 '那能说说大概是什么事吗？' - 第二个播放完后播放")
        print("4. 🚀 用户体验：连续无间隙播放")
    else:
        print("❌ 播放片段数不足")
        print(f"预期至少3个片段，实际播放 {segment_count} 个")

if __name__ == "__main__":
    main()
