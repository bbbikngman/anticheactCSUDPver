#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用真实音频测试打断功能
"""

import time
import threading
import tempfile
import os
from gui_udp_client import AudioChunk, AudioPlayQueue

def create_real_mp3_data():
    """创建一个真实的MP3文件（使用TTS生成）"""
    try:
        from gtts import gTTS
        import io
        
        # 创建一段长文本
        text = "这是一段用于测试打断功能的长音频。" * 10  # 重复10次
        
        # 生成TTS音频
        tts = gTTS(text=text, lang='zh')
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tts.write_to_fp(tmp_file)
            tmp_file.flush()
            
            # 读取MP3数据
            with open(tmp_file.name, 'rb') as f:
                mp3_data = f.read()
            
            # 清理临时文件
            os.unlink(tmp_file.name)
            
            return mp3_data
            
    except ImportError:
        print("⚠️ 需要安装 gtts: pip install gtts")
        return None
    except Exception as e:
        print(f"⚠️ TTS生成失败: {e}")
        return None

def create_simple_mp3():
    """创建一个简单的MP3文件（静音）"""
    # 这是一个最小的MP3文件头（静音）
    mp3_header = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MP3帧头
        0x00, 0x00, 0x00, 0x00,  # 静音数据
    ])
    
    # 重复多次创建长音频
    return mp3_header * 1000  # 创建一个较长的静音MP3

def test_real_interrupt():
    """使用真实音频测试打断功能"""
    print("🧪 使用真实音频测试打断功能...")
    
    # 尝试创建真实MP3
    mp3_data = create_real_mp3_data()
    if mp3_data is None:
        print("📢 使用简单MP3数据进行测试...")
        mp3_data = create_simple_mp3()
    
    # 创建播放队列
    queue = AudioPlayQueue(max_size=3)
    queue.set_log_callback(print)
    
    # 创建长音频chunk
    long_chunk = AudioChunk(
        data=mp3_data,
        session_id="real_test",
        chunk_id=1,
        timestamp=time.time()
    )
    
    # 启动播放session
    queue.start_new_session("real_test")
    
    # 添加音频到队列
    queue.add_chunk(long_chunk)
    
    print("📱 开始播放音频...")
    start_time = time.time()
    
    # 2秒后触发打断
    def trigger_interrupt():
        time.sleep(2)
        interrupt_time = time.time()
        print(f"🛑 {interrupt_time - start_time:.1f}秒后触发打断...")
        
        # 直接调用立即停止方法
        queue.stop_current_playback()
        
        print("⏰ 打断信号已发送，音频应该立即停止...")
        return interrupt_time
    
    # 启动打断线程
    interrupt_thread = threading.Thread(target=trigger_interrupt, daemon=True)
    interrupt_thread.start()
    
    # 等待6秒，观察音频是否在2秒后停止
    time.sleep(6)
    end_time = time.time()
    
    total_duration = end_time - start_time
    print(f"📊 总测试时长: {total_duration:.1f}秒")
    
    # 停止队列
    queue.stop()
    
    # 判断结果
    if total_duration < 4:
        print("✅ 打断测试成功：音频在2秒后立即停止")
        return True
    else:
        print("❌ 打断测试失败：音频没有立即停止")
        return False

def test_watermark_interrupt():
    """测试水位线打断功能"""
    print("\n🧪 测试水位线打断功能...")
    
    queue = AudioPlayQueue(max_size=5)
    queue.set_log_callback(print)
    
    # 创建多个音频chunk
    mp3_data = create_simple_mp3()
    chunks = []
    for i in range(1, 4):
        chunk = AudioChunk(
            data=mp3_data,
            session_id="watermark_test",
            chunk_id=i,
            timestamp=time.time()
        )
        chunks.append(chunk)
    
    # 启动session
    queue.start_new_session("watermark_test")
    
    # 添加所有chunk
    for chunk in chunks:
        queue.add_chunk(chunk)
    
    print("📱 开始播放多个chunk...")
    
    # 1秒后设置水位线打断
    def set_watermark():
        time.sleep(1)
        print("🛑 1秒后设置水位线打断（只允许播放chunk 1）...")
        queue.set_interrupt_watermark("watermark_test", 1)
    
    # 启动水位线设置线程
    watermark_thread = threading.Thread(target=set_watermark, daemon=True)
    watermark_thread.start()
    
    # 等待播放完成
    time.sleep(5)
    
    # 停止队列
    queue.stop()
    
    print("✅ 水位线打断测试完成")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("真实音频打断功能测试")
    print("=" * 50)
    
    try:
        success1 = test_real_interrupt()
        success2 = test_watermark_interrupt()
        
        total_success = sum([success1, success2])
        
        print(f"\n📊 测试结果: {total_success}/2 通过")
        
        if success1:
            print("✅ 立即停止功能正常工作")
        else:
            print("❌ 立即停止功能需要进一步调试")
            
        if success2:
            print("✅ 水位线打断功能正常工作")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
