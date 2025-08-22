#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实流式TTS测试 - 对比HTTP和WebSocket的实际播放时间
测试第一句话的播放开始时间，确保两个版本都能正常播放且不冲突
"""

import time
import re
import threading
import queue
from typing import Generator

def extract_first_sentence(text: str) -> str:
    """提取第一个完整句子"""
    # 中文和英文的句子结束符
    sentence_endings = r'[。！？.!?]'
    
    match = re.search(sentence_endings, text)
    if match:
        return text[:match.end()].strip()
    return ""

class StreamingTTSTest:
    """流式TTS测试类"""
    
    def __init__(self):
        self.tts_module = None
        self.init_tts()
    
    def init_tts(self):
        """初始化TTS模块"""
        try:
            from tts_module import TTSModule
            import config
            self.tts_module = TTSModule(config.DEVICE)
            print("✅ TTS模块初始化成功")
        except Exception as e:
            print(f"❌ TTS模块初始化失败: {e}")
            return False
        return True
    
    def test_current_method(self, ai_module, test_input: str, version_name: str):
        """测试当前方法：等待完整回复后TTS"""
        print(f"\n🔍 测试 {version_name} - 当前方法（等待完整回复）")
        print("-" * 50)
        
        start_time = time.time()
        first_token_time = None
        first_audio_time = None
        
        # 收集完整回复
        full_response = ""
        token_count = 0
        
        try:
            for chunk in ai_module.get_response_stream(test_input):
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"📝 {version_name} 首token时间: {first_token_time - start_time:.3f}s")
                
                full_response += chunk
                token_count += 1
                
                # 显示前几个token
                if token_count <= 10:
                    print(f"Token {token_count}: {chunk}", end="", flush=True)
                elif token_count == 11:
                    print("...", end="", flush=True)
            
            print(f"\n📄 {version_name} 完整回复: {full_response}")
            
            # 开始TTS播放
            print(f"🔊 {version_name} 开始TTS播放...")
            first_audio_time = time.time()
            
            # 实际播放
            self.tts_module.speak(full_response)
            
            # 等待播放完成
            while self.tts_module.is_playing:
                time.sleep(0.1)
            
            end_time = time.time()
            
            # 统计结果
            total_time = end_time - start_time
            first_token_delay = first_token_time - start_time if first_token_time else 0
            first_audio_delay = first_audio_time - start_time if first_audio_time else 0
            
            print(f"📊 {version_name} 当前方法结果:")
            print(f"   首token延迟: {first_token_delay:.3f}s")
            print(f"   首次音频延迟: {first_audio_delay:.3f}s")
            print(f"   总处理时间: {total_time:.3f}s")
            
            return {
                'first_token_delay': first_token_delay,
                'first_audio_delay': first_audio_delay,
                'total_time': total_time,
                'full_response': full_response
            }
            
        except Exception as e:
            print(f"❌ {version_name} 测试失败: {e}")
            return None
    
    def test_streaming_method(self, ai_module, test_input: str, version_name: str):
        """测试流式方法：第一句话立即TTS"""
        print(f"\n🚀 测试 {version_name} - 流式方法（第一句话立即播放）")
        print("-" * 50)
        
        start_time = time.time()
        first_token_time = None
        first_sentence_time = None
        first_audio_time = None
        
        buffer = ""
        full_response = ""
        token_count = 0
        first_sentence_played = False
        
        try:
            for chunk in ai_module.get_response_stream(test_input):
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"📝 {version_name} 流式首token时间: {first_token_time - start_time:.3f}s")
                
                buffer += chunk
                full_response += chunk
                token_count += 1
                
                # 显示前几个token
                if token_count <= 10:
                    print(f"Token {token_count}: {chunk}", end="", flush=True)
                elif token_count == 11:
                    print("...", end="", flush=True)
                
                # 检查是否有完整的第一句话
                if not first_sentence_played:
                    first_sentence = extract_first_sentence(buffer)
                    if first_sentence and len(first_sentence) > 5:  # 确保句子有意义
                        first_sentence_time = time.time()
                        print(f"\n🎯 {version_name} 检测到第一句: {first_sentence}")
                        print(f"⏱️ {version_name} 第一句检测时间: {first_sentence_time - start_time:.3f}s")
                        
                        # 立即播放第一句话
                        print(f"🔊 {version_name} 立即播放第一句...")
                        first_audio_time = time.time()
                        
                        # 在新线程中播放，避免阻塞
                        def play_first_sentence():
                            self.tts_module.speak(first_sentence)
                        
                        threading.Thread(target=play_first_sentence, daemon=True).start()
                        first_sentence_played = True
                        
                        # 等待音频开始播放
                        while not self.tts_module.is_playing:
                            time.sleep(0.001)
                        
                        print(f"✅ {version_name} 第一句开始播放时间: {first_audio_time - start_time:.3f}s")
            
            print(f"\n📄 {version_name} 完整回复: {full_response}")
            
            # 等待第一句播放完成
            if first_sentence_played:
                while self.tts_module.is_playing:
                    time.sleep(0.1)
                print(f"✅ {version_name} 第一句播放完成")
            
            end_time = time.time()
            
            # 统计结果
            total_time = end_time - start_time
            first_token_delay = first_token_time - start_time if first_token_time else 0
            first_sentence_delay = first_sentence_time - start_time if first_sentence_time else 0
            first_audio_delay = first_audio_time - start_time if first_audio_time else 0
            
            print(f"📊 {version_name} 流式方法结果:")
            print(f"   首token延迟: {first_token_delay:.3f}s")
            print(f"   第一句检测延迟: {first_sentence_delay:.3f}s")
            print(f"   首次音频延迟: {first_audio_delay:.3f}s")
            print(f"   总处理时间: {total_time:.3f}s")
            
            return {
                'first_token_delay': first_token_delay,
                'first_sentence_delay': first_sentence_delay,
                'first_audio_delay': first_audio_delay,
                'total_time': total_time,
                'full_response': full_response
            }
            
        except Exception as e:
            print(f"❌ {version_name} 流式测试失败: {e}")
            return None

def main():
    """主测试函数"""
    print("🎵 真实流式TTS对比测试")
    print("=" * 60)
    print("目标：对比HTTP和WebSocket在流式TTS下的实际性能差异")
    print()
    
    # 初始化测试器
    tester = StreamingTTSTest()
    if not tester.tts_module:
        print("❌ 无法初始化TTS，测试终止")
        return
    
    # 初始化AI模块
    try:
        from brain_ai_module import BrainAIModule
        from brain_ai_websocket import BrainAIWebSocketModule
        
        http_ai = BrainAIModule()
        websocket_ai = BrainAIWebSocketModule()
        print("✅ AI模块初始化成功")
    except Exception as e:
        print(f"❌ AI模块初始化失败: {e}")
        return
    
    # 测试输入
    test_input = "他们要我提供验证码"
    print(f"🧪 测试输入: {test_input}")
    
    # 测试结果存储
    results = {}
    
    # 1. HTTP当前方法
    results['http_current'] = tester.test_current_method(http_ai, test_input, "HTTP")
    time.sleep(2)  # 间隔避免冲突
    
    # 2. HTTP流式方法
    results['http_streaming'] = tester.test_streaming_method(http_ai, test_input, "HTTP")
    time.sleep(2)  # 间隔避免冲突
    
    # 3. WebSocket当前方法
    results['websocket_current'] = tester.test_current_method(websocket_ai, test_input, "WebSocket")
    time.sleep(2)  # 间隔避免冲突
    
    # 4. WebSocket流式方法
    results['websocket_streaming'] = tester.test_streaming_method(websocket_ai, test_input, "WebSocket")
    
    # 汇总对比结果
    print("\n" + "=" * 60)
    print("📊 最终对比结果")
    print("=" * 60)
    
    if all(results.values()):
        print("\n🎯 首次音频播报延迟对比:")
        print(f"HTTP 当前方法:     {results['http_current']['first_audio_delay']:.3f}s")
        print(f"HTTP 流式方法:     {results['http_streaming']['first_audio_delay']:.3f}s")
        print(f"WebSocket 当前方法: {results['websocket_current']['first_audio_delay']:.3f}s")
        print(f"WebSocket 流式方法: {results['websocket_streaming']['first_audio_delay']:.3f}s")
        
        # 计算改善
        http_improvement = results['http_current']['first_audio_delay'] - results['http_streaming']['first_audio_delay']
        ws_improvement = results['websocket_current']['first_audio_delay'] - results['websocket_streaming']['first_audio_delay']
        
        print(f"\n🚀 流式方法改善:")
        print(f"HTTP 改善:     {http_improvement:.3f}s ({http_improvement/results['http_current']['first_audio_delay']*100:.1f}%)")
        print(f"WebSocket 改善: {ws_improvement:.3f}s ({ws_improvement/results['websocket_current']['first_audio_delay']*100:.1f}%)")
        
        # WebSocket vs HTTP对比
        ws_vs_http_current = results['websocket_current']['first_audio_delay'] - results['http_current']['first_audio_delay']
        ws_vs_http_streaming = results['websocket_streaming']['first_audio_delay'] - results['http_streaming']['first_audio_delay']
        
        print(f"\n⚡ WebSocket vs HTTP:")
        print(f"当前方法差异: {ws_vs_http_current:.3f}s")
        print(f"流式方法差异: {ws_vs_http_streaming:.3f}s")
        
        if abs(ws_vs_http_streaming) > 0.1:
            winner = "WebSocket" if ws_vs_http_streaming < 0 else "HTTP"
            print(f"🏆 流式方法下 {winner} 更快")
        else:
            print("🤝 流式方法下两者性能相当")

if __name__ == "__main__":
    main()
