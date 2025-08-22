#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试所有片段播放功能
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
        play_time = len(text) * 0.1
        time.sleep(play_time)
        
        self.is_playing = False
        print(f"✅ [TTS] 播放完成: '{text}'")

class StreamingTTSProcessor:
    """流式TTS处理器"""
    
    def __init__(self, tts_module, speaker_wav=None):
        self.tts_module = tts_module
        self.speaker_wav = speaker_wav
    
    def process_streaming_response_simple(self, response_chunks, ai_start_time):
        """简化的流式响应处理 - 播放所有片段"""
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
            print(f"📥 收到chunk: '{chunk}' (buffer: '{buffer}')")
            
            # 检查所有可播放片段
            segments, remaining = extract_playable_segments(buffer)

            # 找出新增的片段（相比已播放的）
            if len(segments) > len(played_segments):
                new_segments = segments[len(played_segments):]

                for segment in new_segments:
                    segment_count = len(played_segments) + 1
                    segment_delay = current_time - ai_start_time
                    print(f"🎯 片段 #{segment_count} 检测 ({segment_delay:.3f}s): '{segment}'")

                    # 立即播放新片段
                    def play_segment(seg=segment, seg_id=segment_count):
                        # 等待前一个播放完成
                        while self.tts_module.is_playing:
                            time.sleep(0.1)

                        print(f"🔊 开始播放片段 #{seg_id}: '{seg}'")
                        self.tts_module.speak(seg, speaker_wav=self.speaker_wav)

                    audio_thread = threading.Thread(target=play_segment, daemon=True)
                    audio_thread.start()

                    # 记录第一个片段的播放开始时间
                    if len(played_segments) == 0:
                        # 等待音频开始播放
                        wait_count = 0
                        while not self.tts_module.is_playing and wait_count < 50:
                            time.sleep(0.01)
                            wait_count += 1

                        if self.tts_module.is_playing:
                            audio_delay = time.time() - ai_start_time
                            print(f"🎵 音频播放开始: {audio_delay:.3f}s")

                    played_segments.append(segment)

            # 不重置buffer，让它继续累积
            
            # 模拟网络延迟
            time.sleep(0.05)
        
        # 处理最后的剩余文本
        if buffer.strip() and len(buffer.strip()) > 2:
            final_segment = buffer.strip()
            segment_count = len(played_segments) + 1
            print(f"🎯 最后片段 #{segment_count}: '{final_segment}'")
            
            def play_final_segment():
                while self.tts_module.is_playing:
                    time.sleep(0.1)
                print(f"🔊 开始播放最后片段: '{final_segment}'")
                self.tts_module.speak(final_segment, speaker_wav=self.speaker_wav)
            
            final_thread = threading.Thread(target=play_final_segment, daemon=True)
            final_thread.start()
            played_segments.append(final_segment)
        
        response_complete_time = time.time()
        total_delay = response_complete_time - ai_start_time
        print(f"📄 AI回复完成: {total_delay:.3f}s，共生成 {len(played_segments)} 个音频片段")
        
        # 等待所有播放完成
        while self.tts_module.is_playing:
            time.sleep(0.1)
        
        return len(played_segments)

def test_all_segments_playback():
    """测试所有片段播放"""
    print("🧪 测试所有片段播放...")
    
    # 模拟AI流式回复
    mock_response = [
        "好", "的", "，", "您", "别", "急", "，", "咱", "们", "慢", "慢", "说", "—", "—", 
        "那", "您", "当", "时", "跟", "对", "方", "说", "了", "哪", "一", "句", "？"
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

def test_expected_segments():
    """测试预期的片段分割"""
    print("\n🔍 测试预期的片段分割...")
    
    full_text = "好的，您别急，咱们慢慢说——那您当时跟对方说了哪一句？"
    segments, remaining = extract_playable_segments(full_text)
    
    print(f"完整文本: '{full_text}'")
    print(f"预期片段: {segments}")
    print(f"剩余文本: '{remaining}'")
    
    expected_segments = ["好的，", "您别急，", "咱们慢慢说——那您当时跟对方说了哪一句？"]
    
    if segments == expected_segments:
        print("✅ 片段分割正确")
        return True
    else:
        print("❌ 片段分割错误")
        print(f"预期: {expected_segments}")
        return False

def main():
    """主测试函数"""
    print("🧪 所有片段播放测试")
    print("=" * 50)
    
    # 测试预期分割
    segments_correct = test_expected_segments()
    
    # 测试播放
    if segments_correct:
        segment_count = test_all_segments_playback()
        
        print("\n" + "=" * 50)
        print("📊 测试结果:")
        
        if segment_count >= 3:  # 预期至少3个片段
            print("✅ 所有片段播放测试通过！")
            print(f"🎯 成功播放 {segment_count} 个片段")
            print("\n💡 预期效果:")
            print("1. 🎵 '好的，' - 立即播放")
            print("2. 🎵 '您别急，' - 第一个播放完后立即播放")
            print("3. 🎵 '咱们慢慢说——那您当时跟对方说了哪一句？' - 第二个播放完后播放")
            print("4. 🚀 用户体验：流畅的连续播放，无间隙")
        else:
            print("❌ 播放片段数不足")
            print(f"预期至少3个片段，实际播放 {segment_count} 个")
    else:
        print("❌ 片段分割测试失败，跳过播放测试")

if __name__ == "__main__":
    main()
