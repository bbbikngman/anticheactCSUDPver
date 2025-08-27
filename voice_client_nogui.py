#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音客户端 - 无GUI版本
用于打包为EXE，避免tkinter依赖问题
"""

import os
import sys
import time
import json
import queue
import socket
import struct
import threading
import tempfile
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import sounddevice as sd

from adpcm_codec import ADPCMCodec, ADPCMProtocol
from websocket_signal import InterruptSignalClient

@dataclass
class AudioChunk:
    """音频块数据结构"""
    session_id: str
    chunk_id: int
    data: bytes
    fragment_index: int = 0
    total_fragments: int = 1

class ConsoleClient:
    """控制台版本的语音客户端"""
    
    def __init__(self):
        # 加载配置
        self.load_config()
        
        # 音频参数
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 512
        
        # 网络连接
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.stream = None
        
        # 音频编解码
        self.codec = ADPCMCodec()
        
        # 播放相关
        self.audio_queue = queue.Queue(maxsize=50)
        self.current_session = None
        self.max_playable_chunk_id = 0
        self.interrupt_event = threading.Event()
        
        # 分片重组
        self.fragment_buffers = {}
        
        # WebSocket信令客户端
        self.interrupt_client = InterruptSignalClient(
            server_host=self.server[0],
            server_port=31004
        )

        # 设置WebSocket回调函数
        self.interrupt_client.set_log_callback(self.log)
        self.interrupt_client.set_interrupt_callback(self._handle_interrupt_signal)
        self.interrupt_client.set_start_session_callback(self._handle_start_session_signal)
        
        print(f"🎙️ 语音客户端初始化完成")
        print(f"📡 服务器地址: {self.server[0]}:{self.server[1]}")
        print(f"🔊 音频参数: {self.sample_rate}Hz, {self.channels}声道")
    
    def load_config(self):
        """加载配置文件"""
        config_file = "client_config.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    server_config = config.get("server", {})
                    self.server = (server_config.get("ip", "127.0.0.1"), 
                                 server_config.get("port", 31000))
            else:
                # 默认配置
                self.server = ("127.0.0.1", 31000)
                print(f"⚠️ 配置文件不存在，使用默认配置: {self.server}")
        except Exception as e:
            print(f"❌ 配置加载失败: {e}")
            self.server = ("127.0.0.1", 31000)
    
    def log(self, message: str):
        """输出日志"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def should_play_chunk(self, chunk: AudioChunk) -> bool:
        """检查chunk是否应该播放（打断逻辑）"""
        # 只播放当前session且chunk_id大于打断水位线的音频
        return (chunk.session_id == self.current_session and
                chunk.chunk_id > self.max_playable_chunk_id)
    
    def start_new_session(self, session_id: str):
        """开始新的播放session"""
        self.log(f"🎵 开始新session: {session_id}")
        self.current_session = session_id
        self.max_playable_chunk_id = 0  # 新session从chunk=1开始播放
    
    def set_interrupt_watermark(self, session_id: str, max_playable_chunk_id: int):
        """设置打断水位线并立即停止当前播放"""
        self.log(f"🛑 设置打断水位线: session={session_id}, max_chunk={max_playable_chunk_id}")
        if session_id == self.current_session:
            self.max_playable_chunk_id = max_playable_chunk_id
            # 立即停止当前播放
            self.stop_current_playback()
            # 短暂延迟后清除打断事件，为新音频播放做准备
            import threading
            threading.Timer(0.1, self.clear_interrupt).start()
    
    def stop_current_playback(self):
        """停止当前播放"""
        self.interrupt_event.set()
        self.log(f"🛑 立即停止当前播放")
    
    def clear_interrupt(self):
        """清除打断事件"""
        self.interrupt_event.clear()
    
    def is_interrupted(self) -> bool:
        """检查是否被打断"""
        return self.interrupt_event.is_set()

    def _handle_interrupt_signal(self, session_id: str, interrupt_after_chunk: int):
        """处理打断信号"""
        self.log(f"🛑 收到打断信号: session={session_id}, after_chunk={interrupt_after_chunk}")
        self.log(f"🛑 处理打断信号: session={session_id}, interrupt_after_chunk={interrupt_after_chunk}")
        self.set_interrupt_watermark(session_id, interrupt_after_chunk)

    def _handle_start_session_signal(self, session_id: str):
        """处理新session信号"""
        self.log(f"🎵 收到新session信号: {session_id}")
        self.start_new_session(session_id)
    
    def _handle_fragmented_audio(self, session_id: str, chunk_id: int, 
                                fragment_index: int, total_fragments: int, 
                                fragment_data: bytes):
        """处理分包音频数据的重组"""
        key = (session_id, chunk_id)
        now = time.time()
        
        # 清理超时的分包缓存（超过5秒）
        expired_keys = []
        for k, buffer_info in self.fragment_buffers.items():
            if now - buffer_info['start_time'] > 5.0:
                expired_keys.append(k)
        for k in expired_keys:
            del self.fragment_buffers[k]
            self.log(f"⚠️ 清理超时分包缓存: session={k[0]}, chunk={k[1]}")
        
        # 初始化或获取分包缓存
        if key not in self.fragment_buffers:
            self.fragment_buffers[key] = {
                'fragments': {},
                'total_fragments': total_fragments,
                'start_time': now
            }
        
        buffer_info = self.fragment_buffers[key]
        buffer_info['fragments'][fragment_index] = fragment_data
        
        received_count = len(buffer_info['fragments'])
        self.log(f"📥 分包缓存: session={session_id}, chunk={chunk_id}, 已收={received_count}/{total_fragments}")
        
        # 检查是否收齐所有分包
        if received_count == total_fragments:
            # 按顺序重组数据
            complete_data = b''
            for i in range(total_fragments):
                if i in buffer_info['fragments']:
                    complete_data += buffer_info['fragments'][i]
                else:
                    self.log(f"❌ 分包 {i} 缺失，重组失败")
                    return None
            
            # 清理缓存
            del self.fragment_buffers[key]
            self.log(f"🎵 分包重组完成，放入播放队列: session={session_id}, chunk={chunk_id}, 总大小={len(complete_data)}字节")
            
            # 创建完整的音频块并放入队列
            chunk = AudioChunk(session_id, chunk_id, complete_data)
            if self.should_play_chunk(chunk):
                try:
                    self.audio_queue.put_nowait(chunk)
                    self.log(f"📥 音频入队: session={session_id}, chunk={chunk_id}, 队列大小={self.audio_queue.qsize()}")
                except queue.Full:
                    self.log(f"⚠️ 音频队列已满，丢弃: session={session_id}, chunk={chunk_id}")
            else:
                self.log(f"⏭️ 跳过chunk: session={session_id}, chunk={chunk_id} (被打断)")
        
        return None
    
    def _recv_loop(self):
        """接收循环"""
        backoff = 0.1
        while self.running:
            try:
                pkt, addr = self.sock.recvfrom(65536)
                backoff = 0.1  # 重置退避时间
                
                # 尝试解析新格式（带session和chunk ID，支持分包）
                try:
                    t, session_id, chunk_id, fragment_index, total_fragments, payload = ADPCMProtocol.unpack_audio_with_session(pkt)
                    if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                        if total_fragments == 1:
                            # 单包，直接处理
                            chunk = AudioChunk(session_id, chunk_id, payload)
                            if self.should_play_chunk(chunk):
                                try:
                                    self.audio_queue.put_nowait(chunk)
                                    self.log(f"📥 音频入队: session={session_id}, chunk={chunk_id}, 队列大小={self.audio_queue.qsize()}")
                                except queue.Full:
                                    self.log(f"⚠️ 音频队列已满，丢弃: session={session_id}, chunk={chunk_id}")
                            else:
                                self.log(f"⏭️ 跳过chunk: session={session_id}, chunk={chunk_id} (被打断)")
                        else:
                            # 分包，需要重组
                            self._handle_fragmented_audio(session_id, chunk_id, fragment_index, total_fragments, payload)
                        continue
                except (ValueError, struct.error):
                    # 新格式解析失败，尝试旧格式
                    pass
                
                # 尝试解析旧格式
                try:
                    t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                    if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                        # 旧格式的TTS音频，创建默认chunk
                        chunk = AudioChunk("unknown", 1, payload)
                        try:
                            self.audio_queue.put_nowait(chunk)
                            self.log(f"📥 音频入队: 旧格式, 队列大小={self.audio_queue.qsize()}")
                        except queue.Full:
                            self.log(f"⚠️ 音频队列已满，丢弃旧格式音频")
                except (ValueError, struct.error):
                    # 都解析失败，忽略
                    pass
                    
            except Exception as e:
                self.log(f"接收错误: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)
    
    def _play_loop(self):
        """播放循环"""
        import pygame
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
        
        while self.running:
            try:
                chunk = self.audio_queue.get(timeout=1.0)
                
                if not self.should_play_chunk(chunk):
                    self.log(f"⏭️ 跳过chunk: session={chunk.session_id}, chunk={chunk.chunk_id} (被打断)")
                    continue
                
                self.log(f"🔊 播放chunk: session={chunk.session_id}, chunk={chunk.chunk_id}")
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                    tmp_file.write(chunk.data)
                    tmp_path = tmp_file.name
                
                self.log(f"📁 临时文件创建: {tmp_path}")
                
                try:
                    # 初始化pygame mixer
                    if not pygame.mixer.get_init():
                        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
                        self.log("🎵 pygame mixer 初始化成功")
                    
                    # 加载并播放音频
                    pygame.mixer.music.load(tmp_path)
                    pygame.mixer.music.play()
                    
                    self.log("▶️ 开始播放音频...")
                    
                    # 等待播放完成或被打断
                    while pygame.mixer.music.get_busy():
                        if self.is_interrupted():
                            pygame.mixer.music.stop()
                            self.log("🛑 检测到打断事件，立即停止播放")
                            break
                        time.sleep(0.1)
                    
                    self.log("✅ 音频播放完成")
                    
                except Exception as e:
                    self.log(f"❌ 播放失败: {e}")
                
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(tmp_path)
                    except Exception as e:
                        self.log(f"⚠️ 临时文件删除失败: {e}")
                        
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"播放循环错误: {e}")
    
    def _audio_callback(self, indata, frames, time, status):
        """音频回调函数"""
        if status:
            self.log(f"音频状态: {status}")
        
        try:
            # 转换为float32并压缩
            block = indata[:, 0].astype(np.float32)
            compressed = self.codec.encode(block)
            pkt = ADPCMProtocol.pack_audio_packet(compressed, ADPCMProtocol.COMPRESSION_ADPCM)
            
            # 调试：检查数据包大小
            if len(pkt) > 1400:
                self.log(f"⚠️ 上行数据包过大: {len(pkt)} 字节，可能被截断")
                
            self.sock.sendto(pkt, self.server)
            
        except Exception as e:
            self.log(f"❌ 音频发送失败: {e}")
    
    def start_stream(self):
        """开始音频流"""
        if self.running:
            return
        
        try:
            # 发送连接信号，触发服务器发送开场白
            hello_pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_HELLO)
            self.sock.sendto(hello_pkt, self.server)
            
            self.stream = sd.InputStream(
                dtype='float32',
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
            
            self.running = True
            self.stream.start()
            
            # 启动WebSocket连接
            self.interrupt_client.start(self.server[0], self.server[1])
            
            # 启动接收和播放线程
            threading.Thread(target=self._recv_loop, daemon=True).start()
            threading.Thread(target=self._play_loop, daemon=True).start()
            
            self.log("🎙️ 已开始采集，等待开场白...")
            
        except Exception as e:
            self.log(f"audio stream error: {e}")
    
    def stop_stream(self):
        """停止音频流"""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.interrupt_client.stop()
        self.log("🛑 音频流已停止")
    
    def reset_session(self):
        """重置会话"""
        try:
            pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_RESET)
            self.sock.sendto(pkt, self.server)
            self.codec.reset_all()
            self.log("🧹 已请求服务器重置会话")
        except Exception as e:
            self.log(f"reset error: {e}")

def main():
    """主函数"""
    print("🎙️ 语音客户端启动中...")
    print("=" * 50)
    
    client = ConsoleClient()
    
    try:
        client.start_stream()
        
        print("\n控制命令:")
        print("  输入 'quit' 或 'exit' 退出")
        print("  输入 'reset' 重置会话")
        print("  按 Ctrl+C 强制退出")
        print("=" * 50)
        
        while True:
            try:
                cmd = input().strip().lower()
                if cmd in ['quit', 'exit', 'q']:
                    break
                elif cmd == 'reset':
                    client.reset_session()
                elif cmd == 'help':
                    print("可用命令: quit, exit, reset, help")
            except KeyboardInterrupt:
                break
            except EOFError:
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        client.stop_stream()
        print("\n👋 客户端已退出")

if __name__ == "__main__":
    main()
