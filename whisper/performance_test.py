#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP vs WebSocket 性能对比测试
"""

import time
import statistics
from typing import List

def test_ai_performance_with_tts(ai_module, tts_module, test_queries: List[str], mode_name: str):
    """测试AI模块性能 - 重点测试到语音播报的时间"""
    print(f"\n🔍 测试 {mode_name} 模式性能 (包含TTS播报时间)...")
    print("=" * 60)

    response_times = []
    first_token_times = []
    first_audio_times = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n测试 {i}/{len(test_queries)}: {query}")

        # 记录请求开始时间
        request_start_time = time.time()
        first_token_received = False
        first_audio_started = False
        full_response = ""

        try:
            response_stream = ai_module.get_response_stream(query)

            # 创建一个生成器来监控TTS开始时间
            def monitored_stream():
                nonlocal first_token_received, first_audio_started
                for chunk in response_stream:
                    if not first_token_received:
                        first_token_time = time.time()
                        first_token_delay = first_token_time - request_start_time
                        first_token_times.append(first_token_delay)
                        first_token_received = True
                        print(f"   📝 首token延迟: {first_token_delay:.3f}s")

                    yield chunk

            # 监控TTS开始时间
            def tts_start_monitor():
                nonlocal first_audio_started
                # 等待TTS开始播放
                while not tts_module.is_playing:
                    time.sleep(0.001)  # 1ms检查间隔

                if not first_audio_started:
                    first_audio_time = time.time()
                    first_audio_delay = first_audio_time - request_start_time
                    first_audio_times.append(first_audio_delay)
                    first_audio_started = True
                    print(f"   🔊 首次音频播报延迟: {first_audio_delay:.3f}s")

            # 启动TTS监控线程
            import threading
            monitor_thread = threading.Thread(target=tts_start_monitor)
            monitor_thread.daemon = True
            monitor_thread.start()

            # 开始TTS播放
            tts_module.speak_stream(monitored_stream())

            # 等待播放完成
            while tts_module.is_playing:
                time.sleep(0.1)

            end_time = time.time()
            total_time = end_time - request_start_time
            response_times.append(total_time)

            print(f"   ⏱️ 总处理时间: {total_time:.3f}s")
            print(f"   📄 回复长度: {len(full_response)} 字符")

        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            continue

        # 间隔2秒避免API限制和TTS冲突
        time.sleep(2)
    
    # 统计结果
    if response_times:
        print(f"\n📊 {mode_name} 模式性能统计:")
        print(f"   测试次数: {len(response_times)}")
        print(f"   平均总处理时间: {statistics.mean(response_times):.3f}s")
        print(f"   最快处理: {min(response_times):.3f}s")
        print(f"   最慢处理: {max(response_times):.3f}s")

        if first_token_times:
            print(f"   平均首token延迟: {statistics.mean(first_token_times):.3f}s")
            print(f"   最快首token: {min(first_token_times):.3f}s")
            print(f"   最慢首token: {max(first_token_times):.3f}s")

        if first_audio_times:
            print(f"   🎯 平均首次音频播报延迟: {statistics.mean(first_audio_times):.3f}s")
            print(f"   🎯 最快音频播报: {min(first_audio_times):.3f}s")
            print(f"   🎯 最慢音频播报: {max(first_audio_times):.3f}s")

    return response_times, first_token_times, first_audio_times

def main():
    """主测试函数"""
    print("🚀 HTTP vs WebSocket 性能对比测试")
    print("=" * 60)
    
    # 测试查询列表
    test_queries = [
        "您好",
        "我没有接到这样的电话",
        "对方说是银行的",
        "他们要我提供验证码",
        "我应该怎么办？"
    ]
    
    print("测试查询列表:")
    for i, query in enumerate(test_queries, 1):
        print(f"  {i}. {query}")
    
    # 初始化AI和TTS模块
    try:
        print("\n🔧 初始化AI和TTS模块...")

        from brain_ai_module import BrainAIModule
        from brain_ai_websocket import BrainAIWebSocketModule
        from tts_module import TTSModule
        import config

        http_ai = BrainAIModule()
        websocket_ai = BrainAIWebSocketModule()
        tts = TTSModule(config.DEVICE)

        print("✅ AI和TTS模块初始化成功")

    except Exception as e:
        print(f"❌ 模块初始化失败: {e}")
        return

    # 测试HTTP模式
    http_times, http_first_token, http_audio = test_ai_performance_with_tts(
        http_ai, tts, test_queries, "HTTP流式"
    )

    print("\n" + "="*60)

    # 测试WebSocket模式
    websocket_times, websocket_first_token, websocket_audio = test_ai_performance_with_tts(
        websocket_ai, tts, test_queries, "WebSocket流式"
    )
    
    # 对比结果
    print("\n" + "="*60)
    print("🏆 性能对比结果")
    print("="*60)
    
    if http_times and websocket_times:
        http_avg = statistics.mean(http_times)
        websocket_avg = statistics.mean(websocket_times)
        
        print(f"HTTP平均响应时间:     {http_avg:.2f}s")
        print(f"WebSocket平均响应时间: {websocket_avg:.2f}s")
        
        if http_avg < websocket_avg:
            improvement = ((websocket_avg - http_avg) / websocket_avg) * 100
            print(f"🎯 HTTP模式更快，快了 {improvement:.1f}%")
        else:
            improvement = ((http_avg - websocket_avg) / http_avg) * 100
            print(f"🎯 WebSocket模式更快，快了 {improvement:.1f}%")
        
        # 首token对比
        if http_first_token and websocket_first_token:
            http_first_avg = statistics.mean(http_first_token)
            websocket_first_avg = statistics.mean(websocket_first_token)
            
            print(f"\nHTTP首token延迟:     {http_first_avg:.2f}s")
            print(f"WebSocket首token延迟: {websocket_first_avg:.2f}s")
            
            if http_first_avg < websocket_first_avg:
                first_improvement = ((websocket_first_avg - http_first_avg) / websocket_first_avg) * 100
                print(f"🚀 HTTP首token更快，快了 {first_improvement:.1f}%")
            else:
                first_improvement = ((http_first_avg - websocket_first_avg) / http_first_avg) * 100
                print(f"🚀 WebSocket首token更快，快了 {first_improvement:.1f}%")
    
    print("\n" + "="*60)
    print("📝 测试结论:")
    print("1. 在远程API环境下，两种方式的性能差异主要来自网络和API处理")
    print("2. HTTP流式API通常更稳定，WebSocket可能有连接开销")
    print("3. 实际性能还受网络状况、API负载等因素影响")
    print("4. 建议在实际使用环境中进行长期测试")

if __name__ == "__main__":
    main()
