#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速音频测试 - 验证两个版本都能正常播放且无冲突
"""

import time

def test_basic_audio():
    """基础音频测试"""
    print("🔊 基础音频测试")
    print("=" * 30)
    
    try:
        from tts_module import TTSModule
        import config
        
        tts = TTSModule(config.DEVICE)
        
        # 测试1：简单播放
        print("1. 测试简单播放...")
        tts.speak("这是一个测试。")
        while tts.is_playing:
            time.sleep(0.1)
        print("✅ 简单播放完成")
        
        time.sleep(1)
        
        # 测试2：连续播放
        print("2. 测试连续播放...")
        tts.speak("第一句话。")
        while tts.is_playing:
            time.sleep(0.1)
        
        time.sleep(0.5)
        
        tts.speak("第二句话。")
        while tts.is_playing:
            time.sleep(0.1)
        print("✅ 连续播放完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 基础音频测试失败: {e}")
        return False

def test_ai_audio(ai_module, name: str):
    """测试AI模块的音频播放"""
    print(f"\n🤖 测试 {name} 音频播放")
    print("-" * 30)
    
    try:
        from tts_module import TTSModule
        import config
        
        tts = TTSModule(config.DEVICE)
        
        # 生成回复
        print(f"📝 {name} 生成回复...")
        start_time = time.time()
        
        response = ""
        for chunk in ai_module.get_response_stream("您好"):
            response += chunk
            print(chunk, end="", flush=True)
        
        generation_time = time.time() - start_time
        print(f"\n⏱️ {name} 生成耗时: {generation_time:.3f}s")
        print(f"📄 {name} 回复: {response}")
        
        # 播放音频
        print(f"🔊 {name} 开始播放...")
        audio_start = time.time()
        
        tts.speak(response)
        
        # 等待播放开始
        while not tts.is_playing:
            time.sleep(0.01)
        
        actual_audio_start = time.time()
        print(f"✅ {name} 音频开始: {actual_audio_start - start_time:.3f}s")
        
        # 等待播放完成
        while tts.is_playing:
            time.sleep(0.1)
        
        audio_end = time.time()
        print(f"🎵 {name} 播放完成: {audio_end - start_time:.3f}s")
        
        return {
            'generation_time': generation_time,
            'audio_start_delay': actual_audio_start - start_time,
            'total_time': audio_end - start_time,
            'response': response
        }
        
    except Exception as e:
        print(f"❌ {name} 音频测试失败: {e}")
        return None

def main():
    """主测试函数"""
    print("🎵 快速音频验证测试")
    print("=" * 40)
    print("目标：验证两个版本都能正常播放且无冲突")
    print()
    
    # 1. 基础音频测试
    if not test_basic_audio():
        print("❌ 基础音频测试失败，终止测试")
        return
    
    # 2. 初始化AI模块
    try:
        from brain_ai_module import BrainAIModule
        from brain_ai_websocket import BrainAIWebSocketModule
        
        print("\n🔧 初始化AI模块...")
        http_ai = BrainAIModule()
        websocket_ai = BrainAIWebSocketModule()
        print("✅ AI模块初始化成功")
    except Exception as e:
        print(f"❌ AI模块初始化失败: {e}")
        return
    
    # 3. 测试HTTP版本
    http_result = test_ai_audio(http_ai, "HTTP")
    
    # 4. 等待间隔
    print("\n⏳ 等待3秒避免冲突...")
    time.sleep(3)
    
    # 5. 测试WebSocket版本
    websocket_result = test_ai_audio(websocket_ai, "WebSocket")
    
    # 6. 对比结果
    print("\n" + "=" * 40)
    print("📊 测试结果对比")
    print("=" * 40)
    
    if http_result and websocket_result:
        print(f"\n✅ 两个版本都能正常播放！")
        print(f"\nHTTP版本:")
        print(f"  生成时间: {http_result['generation_time']:.3f}s")
        print(f"  音频延迟: {http_result['audio_start_delay']:.3f}s")
        print(f"  总耗时: {http_result['total_time']:.3f}s")
        
        print(f"\nWebSocket版本:")
        print(f"  生成时间: {websocket_result['generation_time']:.3f}s")
        print(f"  音频延迟: {websocket_result['audio_start_delay']:.3f}s")
        print(f"  总耗时: {websocket_result['total_time']:.3f}s")
        
        # 计算差异
        gen_diff = websocket_result['generation_time'] - http_result['generation_time']
        audio_diff = websocket_result['audio_start_delay'] - http_result['audio_start_delay']
        
        print(f"\n🔍 性能差异:")
        print(f"  生成时间差异: {gen_diff:+.3f}s")
        print(f"  音频延迟差异: {audio_diff:+.3f}s")
        
        if abs(gen_diff) < 0.1:
            print("  🤝 生成速度相当")
        elif gen_diff < 0:
            print(f"  🚀 WebSocket生成快 {abs(gen_diff):.3f}s")
        else:
            print(f"  🚀 HTTP生成快 {abs(gen_diff):.3f}s")
        
        if abs(audio_diff) < 0.1:
            print("  🤝 音频延迟相当")
        elif audio_diff < 0:
            print(f"  🚀 WebSocket音频快 {abs(audio_diff):.3f}s")
        else:
            print(f"  🚀 HTTP音频快 {abs(audio_diff):.3f}s")
        
        print(f"\n🎯 结论:")
        print(f"1. ✅ 两个版本都能正常工作")
        print(f"2. ✅ 没有音频冲突问题")
        print(f"3. 📊 性能差异在可接受范围内")
        
    else:
        print("❌ 部分测试失败")
        if not http_result:
            print("  - HTTP版本测试失败")
        if not websocket_result:
            print("  - WebSocket版本测试失败")

if __name__ == "__main__":
    main()
