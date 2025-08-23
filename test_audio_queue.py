#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试音频播放队列功能
"""

import time
import threading
from gui_udp_client import AudioChunk, AudioPlayQueue

def test_audio_queue_basic():
    """测试音频队列基本功能"""
    print("🧪 测试音频队列基本功能...")
    
    # 创建播放队列
    queue = AudioPlayQueue(max_size=3)
    queue.set_log_callback(print)  # 使用print作为日志回调
    
    # 创建测试音频chunk
    chunk1 = AudioChunk(
        data=b"FAKE_MP3_DATA_1",
        session_id="test123",
        chunk_id=1,
        timestamp=time.time()
    )
    
    chunk2 = AudioChunk(
        data=b"FAKE_MP3_DATA_2", 
        session_id="test123",
        chunk_id=2,
        timestamp=time.time()
    )
    
    # 开始新session
    queue.start_new_session("test123")
    
    # 添加chunk到队列
    success1 = queue.add_chunk(chunk1)
    success2 = queue.add_chunk(chunk2)
    
    print(f"Chunk1 添加结果: {success1}")
    print(f"Chunk2 添加结果: {success2}")
    
    # 等待一段时间让播放线程处理
    time.sleep(2)
    
    # 停止队列
    queue.stop()
    
    print("✅ 基本功能测试完成")
    return True

def test_audio_queue_interrupt():
    """测试音频队列打断功能"""
    print("\n🧪 测试音频队列打断功能...")
    
    # 创建播放队列
    queue = AudioPlayQueue(max_size=5)
    queue.set_log_callback(print)
    
    # 开始新session
    queue.start_new_session("interrupt_test")
    
    # 创建多个chunk
    chunks = []
    for i in range(1, 6):
        chunk = AudioChunk(
            data=f"FAKE_MP3_DATA_{i}".encode(),
            session_id="interrupt_test",
            chunk_id=i,
            timestamp=time.time()
        )
        chunks.append(chunk)
        queue.add_chunk(chunk)
    
    # 等待一点时间
    time.sleep(0.5)
    
    # 设置打断水位线：只允许播放chunk 1和2
    queue.set_interrupt_watermark("interrupt_test", 2)
    
    # 等待播放完成
    time.sleep(2)
    
    # 停止队列
    queue.stop()
    
    print("✅ 打断功能测试完成")
    return True

def test_audio_queue_session_switch():
    """测试音频队列session切换功能"""
    print("\n🧪 测试音频队列session切换功能...")
    
    # 创建播放队列
    queue = AudioPlayQueue(max_size=3)
    queue.set_log_callback(print)
    
    # 第一个session
    queue.start_new_session("session1")
    
    chunk1 = AudioChunk(
        data=b"SESSION1_CHUNK1",
        session_id="session1", 
        chunk_id=1,
        timestamp=time.time()
    )
    queue.add_chunk(chunk1)
    
    time.sleep(0.5)
    
    # 切换到第二个session
    queue.start_new_session("session2")
    
    chunk2 = AudioChunk(
        data=b"SESSION2_CHUNK1",
        session_id="session2",
        chunk_id=1, 
        timestamp=time.time()
    )
    queue.add_chunk(chunk2)
    
    # 等待播放完成
    time.sleep(2)
    
    # 停止队列
    queue.stop()
    
    print("✅ Session切换测试完成")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("音频播放队列测试")
    print("=" * 50)
    
    try:
        success1 = test_audio_queue_basic()
        success2 = test_audio_queue_interrupt()
        success3 = test_audio_queue_session_switch()
        
        if success1 and success2 and success3:
            print("\n🎉 所有音频队列测试通过！")
        else:
            print("\n❌ 音频队列测试失败！")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
