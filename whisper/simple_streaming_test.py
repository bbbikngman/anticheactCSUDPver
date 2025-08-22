#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化流式TTS测试 - 重点验证第一句话播放时间和冲突问题
"""

import time
import re
import threading

def extract_first_sentence(text: str) -> str:
    """提取第一个完整句子"""
    sentence_endings = r'[。！？.!?]'
    match = re.search(sentence_endings, text)
    if match:
        return text[:match.end()].strip()
    return ""

def test_ai_with_streaming_tts(ai_module, module_name: str, test_input: str):
    """测试AI模块的流式TTS性能"""
    print(f"\n🔍 测试 {module_name}")
    print("=" * 40)
    
    start_time = time.time()
    first_token_time = None
    first_sentence_time = None
    first_audio_time = None
    
    buffer = ""
    full_response = ""
    first_sentence_found = False
    
    try:
        # 初始化TTS
        from tts_module import TTSModule
        import config
        tts = TTSModule(config.DEVICE)
        
        print(f"📝 {module_name} 开始生成回复...")
        
        for chunk in ai_module.get_response_stream(test_input):
            current_time = time.time()
            
            # 记录首token时间
            if first_token_time is None:
                first_token_time = current_time
                print(f"⚡ {module_name} 首token: {first_token_time - start_time:.3f}s")
            
            buffer += chunk
            full_response += chunk
            print(chunk, end="", flush=True)
            
            # 检查第一句话
            if not first_sentence_found:
                first_sentence = extract_first_sentence(buffer)
                if first_sentence and len(first_sentence) > 8:  # 确保句子有意义
                    first_sentence_time = current_time
                    first_sentence_found = True
                    
                    print(f"\n🎯 {module_name} 第一句: {first_sentence}")
                    print(f"⏱️ {module_name} 第一句时间: {first_sentence_time - start_time:.3f}s")
                    
                    # 立即播放第一句
                    print(f"🔊 {module_name} 开始播放第一句...")
                    first_audio_time = time.time()
                    
                    def play_audio():
                        tts.speak(first_sentence)
                    
                    # 在新线程播放避免阻塞
                    audio_thread = threading.Thread(target=play_audio, daemon=True)
                    audio_thread.start()
                    
                    # 等待播放开始
                    wait_count = 0
                    while not tts.is_playing and wait_count < 50:  # 最多等5秒
                        time.sleep(0.1)
                        wait_count += 1
                    
                    if tts.is_playing:
                        actual_audio_start = time.time()
                        print(f"✅ {module_name} 音频开始播放: {actual_audio_start - start_time:.3f}s")
                        
                        # 等待播放完成
                        while tts.is_playing:
                            time.sleep(0.1)
                        print(f"🎵 {module_name} 第一句播放完成")
                    else:
                        print(f"⚠️ {module_name} 音频播放启动失败")
        
        print(f"\n📄 {module_name} 完整回复: {full_response}")
        
        end_time = time.time()
        
        # 统计结果
        results = {
            'first_token_delay': first_token_time - start_time if first_token_time else 0,
            'first_sentence_delay': first_sentence_time - start_time if first_sentence_time else 0,
            'first_audio_delay': first_audio_time - start_time if first_audio_time else 0,
            'total_time': end_time - start_time,
            'full_response': full_response
        }
        
        print(f"\n📊 {module_name} 性能统计:")
        print(f"   首token延迟: {results['first_token_delay']:.3f}s")
        print(f"   第一句检测: {results['first_sentence_delay']:.3f}s")
        print(f"   🎯 首次音频: {results['first_audio_delay']:.3f}s")
        print(f"   总处理时间: {results['total_time']:.3f}s")
        
        return results
        
    except Exception as e:
        print(f"❌ {module_name} 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主测试函数"""
    print("🎵 流式TTS性能对比测试")
    print("=" * 50)
    print("重点验证：第一句话播放开始时间 & 无冲突播放")
    print()
    
    # 初始化AI模块
    try:
        from brain_ai_module import BrainAIModule
        from brain_ai_websocket import BrainAIWebSocketModule
        
        print("🔧 初始化AI模块...")
        http_ai = BrainAIModule()
        websocket_ai = BrainAIWebSocketModule()
        print("✅ AI模块初始化成功")
    except Exception as e:
        print(f"❌ AI模块初始化失败: {e}")
        return
    
    # 测试输入
    test_input = "他们要我提供验证码"
    print(f"🧪 测试输入: '{test_input}'")
    
    # 测试HTTP版本
    print("\n" + "🔴" * 20 + " HTTP测试 " + "🔴" * 20)
    http_result = test_ai_with_streaming_tts(http_ai, "HTTP", test_input)
    
    # 等待间隔，避免冲突
    print("\n⏳ 等待3秒避免音频冲突...")
    time.sleep(3)
    
    # 测试WebSocket版本
    print("\n" + "🔵" * 20 + " WebSocket测试 " + "🔵" * 20)
    websocket_result = test_ai_with_streaming_tts(websocket_ai, "WebSocket", test_input)
    
    # 对比结果
    print("\n" + "🏆" * 20 + " 最终对比 " + "🏆" * 20)
    
    if http_result and websocket_result:
        print(f"\n🎯 关键指标对比:")
        print(f"{'指标':<15} {'HTTP':<10} {'WebSocket':<12} {'差异':<10}")
        print("-" * 50)
        
        # 首token延迟
        token_diff = websocket_result['first_token_delay'] - http_result['first_token_delay']
        print(f"{'首token延迟':<15} {http_result['first_token_delay']:.3f}s    {websocket_result['first_token_delay']:.3f}s      {token_diff:+.3f}s")
        
        # 首次音频延迟
        audio_diff = websocket_result['first_audio_delay'] - http_result['first_audio_delay']
        print(f"{'首次音频延迟':<15} {http_result['first_audio_delay']:.3f}s    {websocket_result['first_audio_delay']:.3f}s      {audio_diff:+.3f}s")
        
        # 总处理时间
        total_diff = websocket_result['total_time'] - http_result['total_time']
        print(f"{'总处理时间':<15} {http_result['total_time']:.3f}s    {websocket_result['total_time']:.3f}s      {total_diff:+.3f}s")
        
        print(f"\n🔍 分析结果:")
        if abs(audio_diff) < 0.1:
            print("🤝 两种方案在流式TTS下性能相当")
        elif audio_diff < 0:
            print(f"🚀 WebSocket在首次音频播放上快 {abs(audio_diff):.3f}s")
        else:
            print(f"🚀 HTTP在首次音频播放上快 {abs(audio_diff):.3f}s")
        
        if abs(token_diff) > 0.05:
            faster_token = "WebSocket" if token_diff < 0 else "HTTP"
            print(f"⚡ {faster_token} 在首token上快 {abs(token_diff):.3f}s")
        
        print(f"\n💡 关键发现:")
        print(f"1. 流式TTS让首次音频播放提前到第一句检测时")
        print(f"2. WebSocket的首token优势: {abs(token_diff):.3f}s")
        print(f"3. 实际用户体验差异: {abs(audio_diff):.3f}s")
        
        if abs(audio_diff) > 0.1:
            print(f"4. 🎯 流式TTS确实让WebSocket优势体现出来了！")
        else:
            print(f"4. 🤔 即使在流式TTS下，两者差异仍然很小")
    
    else:
        print("❌ 测试失败，无法进行对比")

if __name__ == "__main__":
    main()
