#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试打断播放功能
"""

import time
import threading
from gui_udp_client import AudioChunk, AudioPlayQueue

def create_test_mp3_data(duration_seconds=5):
    """创建测试用的MP3数据（模拟长音频）"""
    # 这里创建一个假的MP3头部，实际测试时会用pygame播放
    mp3_header = b'\xff\xfb\x90\x00'  # MP3帧头
    # 模拟长音频数据
    fake_audio_data = b'\x00' * (duration_seconds * 1000)  # 每秒1KB数据
    return mp3_header + fake_audio_data

def test_interrupt_current_playback():
    """测试打断当前播放的音频"""
    print("🧪 测试打断当前播放的音频...")
    
    # 创建播放队列
    queue = AudioPlayQueue(max_size=3)
    queue.set_log_callback(print)
    
    # 创建一个长音频chunk（5秒）
    long_audio_data = create_test_mp3_data(duration_seconds=5)
    long_chunk = AudioChunk(
        data=long_audio_data,
        session_id="test_session",
        chunk_id=1,
        timestamp=time.time()
    )
    
    # 启动播放session
    queue.start_new_session("test_session")
    
    # 添加长音频到队列
    queue.add_chunk(long_chunk)
    
    print("📱 开始播放长音频（5秒）...")
    
    # 等待2秒后触发打断
    def trigger_interrupt():
        time.sleep(2)
        print("🛑 2秒后触发打断...")
        
        # 设置打断水位线（应该立即停止当前播放）
        queue.set_interrupt_watermark("test_session", 0)  # 不允许播放任何chunk
        
        print("⏰ 打断信号已发送，检查音频是否立即停止...")
    
    # 启动打断线程
    interrupt_thread = threading.Thread(target=trigger_interrupt, daemon=True)
    interrupt_thread.start()
    
    # 等待总共6秒，看看音频是否在2秒后立即停止
    start_time = time.time()
    time.sleep(6)
    end_time = time.time()
    
    actual_duration = end_time - start_time
    print(f"📊 实际播放时长: {actual_duration:.1f}秒")
    
    # 停止队列
    queue.stop()
    
    # 判断测试结果
    if actual_duration < 4:  # 如果总时长小于4秒，说明打断生效了
        print("✅ 打断测试通过：音频在2秒后立即停止")
        return True
    else:
        print("❌ 打断测试失败：音频没有立即停止，继续播放了完整的5秒")
        return False

def test_interrupt_queue_only():
    """测试仅队列打断（不停止当前播放）"""
    print("\n🧪 测试仅队列打断功能...")
    
    queue = AudioPlayQueue(max_size=5)
    queue.set_log_callback(print)
    
    # 创建多个短音频chunk
    chunks = []
    for i in range(1, 4):
        chunk = AudioChunk(
            data=create_test_mp3_data(duration_seconds=1),
            session_id="queue_test",
            chunk_id=i,
            timestamp=time.time()
        )
        chunks.append(chunk)
    
    # 启动session
    queue.start_new_session("queue_test")
    
    # 添加所有chunk
    for chunk in chunks:
        queue.add_chunk(chunk)
    
    # 立即设置打断水位线，只允许播放chunk 1
    time.sleep(0.1)  # 稍等一下让第一个chunk开始播放
    queue.set_interrupt_watermark("queue_test", 1)
    
    # 等待播放完成
    time.sleep(3)
    
    # 停止队列
    queue.stop()
    
    print("✅ 队列打断测试完成（应该只播放了chunk 1）")
    return True

def test_immediate_stop_functionality():
    """测试立即停止功能（如果实现了的话）"""
    print("\n🧪 测试立即停止功能...")
    
    queue = AudioPlayQueue(max_size=3)
    queue.set_log_callback(print)
    
    # 检查是否有立即停止方法
    if hasattr(queue, 'stop_current_playback'):
        print("✅ 发现 stop_current_playback 方法")
        
        # 创建长音频
        long_chunk = AudioChunk(
            data=create_test_mp3_data(duration_seconds=3),
            session_id="stop_test",
            chunk_id=1,
            timestamp=time.time()
        )
        
        # 启动播放
        queue.start_new_session("stop_test")
        queue.add_chunk(long_chunk)
        
        # 1秒后立即停止
        time.sleep(1)
        print("🛑 调用立即停止方法...")
        queue.stop_current_playback()
        
        # 再等待2秒，看看是否真的停止了
        time.sleep(2)
        
        queue.stop()
        print("✅ 立即停止功能测试完成")
        return True
    else:
        print("❌ 未找到 stop_current_playback 方法，需要实现")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("打断播放功能测试")
    print("=" * 50)
    
    try:
        # 注意：这些测试使用假的MP3数据，pygame可能无法播放
        # 但可以测试队列逻辑和线程行为
        
        print("⚠️ 注意：使用假MP3数据测试，pygame可能报错但不影响逻辑测试")
        
        success1 = test_interrupt_current_playback()
        success2 = test_interrupt_queue_only() 
        success3 = test_immediate_stop_functionality()
        
        total_success = sum([success1, success2, success3])
        
        print(f"\n📊 测试结果: {total_success}/3 通过")
        
        if total_success < 3:
            print("\n💡 建议实现以下功能：")
            print("1. AudioPlayQueue.stop_current_playback() - 立即停止当前播放")
            print("2. 在 set_interrupt_watermark() 中调用立即停止")
            print("3. 使用 pygame.mixer.music.stop() 强制停止播放")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
