#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI UDP 客户端（最小改动版）
- Start：开始麦克风采集（16k/mono/512），ADPCM 压缩后 UDP 发送
- Reset：发送控制包，提示词级重置（服务器清理该客户端会话）
- 日志：窗口内滚动文本日志 + 控制台日志（便于调试与打包 onedir）
"""

import socket
import threading
import time
import queue
import tempfile
import os
import logging
import json
import struct
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
from tkinter import Tk, Button, Text, END, DISABLED, NORMAL, PhotoImage

from adpcm_codec import ADPCMCodec, ADPCMProtocol
from websocket_signal import InterruptSignalClient

@dataclass
class AudioChunk:
    """音频块数据结构"""
    data: bytes
    session_id: str
    chunk_id: int
    timestamp: float

class AudioPlayQueue:
    """音频播放队列，支持打断功能"""

    def __init__(self, max_size=5):
        self.queue = queue.Queue(max_size)
        self.current_session = ""
        self.max_playable_chunk_id = float('inf')  # 打断水位线
        self.playing = False
        self.play_thread = None
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()  # 打断当前播放事件
        self.log_callback = None  # 日志回调函数

    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback

    def log(self, message):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def add_chunk(self, chunk: AudioChunk) -> bool:
        """添加音频chunk到队列"""
        try:
            self.queue.put_nowait(chunk)
            self.log(f"📥 音频入队: session={chunk.session_id}, chunk={chunk.chunk_id}, 队列大小={self.queue.qsize()}")
            return True
        except queue.Full:
            self.log("⚠️ 音频队列已满，丢弃最旧的chunk")
            try:
                # 移除最旧的chunk
                old_chunk = self.queue.get_nowait()
                self.log(f"🗑️ 丢弃旧chunk: session={old_chunk.session_id}, chunk={old_chunk.chunk_id}")
                # 添加新chunk
                self.queue.put_nowait(chunk)
                self.log(f"📥 音频入队: session={chunk.session_id}, chunk={chunk.chunk_id}, 队列大小={self.queue.qsize()}")
                return True
            except queue.Empty:
                return False

    def should_play_chunk(self, chunk: AudioChunk) -> bool:
        """检查chunk是否应该播放（打断逻辑）"""
        # 只播放当前session且chunk_id大于打断水位线的音频
        return (chunk.session_id == self.current_session and
                chunk.chunk_id > self.max_playable_chunk_id)

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
        """立即停止当前播放的音频"""
        self.log("🛑 立即停止当前播放")
        self.interrupt_event.set()  # 设置打断事件

    def is_interrupted(self) -> bool:
        """检查是否收到打断信号"""
        return self.interrupt_event.is_set()

    def clear_interrupt(self):
        """清除打断信号"""
        self.interrupt_event.clear()

    def start_new_session(self, session_id: str):
        """开始新的播放session"""
        self.log(f"🎵 开始新session: {session_id}")
        self.current_session = session_id
        self.max_playable_chunk_id = 0  # 新session从chunk=1开始播放

        # 启动播放线程（如果还没启动）
        if not self.playing:
            self.playing = True
            self.stop_event.clear()
            self.play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self.play_thread.start()
            self.log("🎵 播放线程已启动")

    def stop(self):
        """停止播放队列"""
        self.playing = False
        self.stop_event.set()
        if self.play_thread and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)
        self.log("🛑 播放队列已停止")

    def _play_loop(self):
        """播放循环线程"""
        self.log("🎵 播放线程开始运行")
        while self.playing and not self.stop_event.is_set():
            try:
                # 从队列获取音频chunk，超时1秒
                chunk = self.queue.get(timeout=1.0)

                # 检查是否应该播放这个chunk
                if self.should_play_chunk(chunk):
                    self.log(f"🔊 播放chunk: session={chunk.session_id}, chunk={chunk.chunk_id}")
                    self._play_chunk_data(chunk.data)
                else:
                    self.log(f"⏭️ 跳过chunk: session={chunk.session_id}, chunk={chunk.chunk_id} (被打断)")

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                self.log(f"❌ 播放错误: {e}")

        self.log("🎵 播放线程结束")

    def _play_chunk_data(self, data: bytes):
        """播放单个chunk的数据"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(data)
                path = tmp.name

            self.log(f"📁 临时文件创建: {path}")

            try:
                import pygame

                # 重新初始化mixer，确保干净状态
                if pygame.mixer.get_init():
                    pygame.mixer.quit()

                pygame.mixer.init()
                self.log("🎵 pygame mixer 初始化成功")

                # 加载并播放音频
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self.log("▶️ 开始播放音频...")

                # 等待播放完成，同时检查打断事件
                while pygame.mixer.music.get_busy():
                    if self.stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    if self.is_interrupted():
                        self.log("🛑 检测到打断事件，立即停止播放")
                        pygame.mixer.music.stop()
                        self.clear_interrupt()  # 清除打断事件
                        break
                    time.sleep(0.1)

                self.log("✅ 音频播放完成")

            except Exception as e:
                self.log(f"❌ pygame播放失败: {e}")
            finally:
                # 清理临时文件
                try:
                    os.unlink(path)
                    self.log(f"🗑️ 临时文件已删除: {path}")
                except Exception as e:
                    self.log(f"⚠️ 临时文件删除失败: {e}")

        except Exception as e:
            self.log(f"❌ 播放chunk失败: {e}")

def load_config(config_file="client_config.json"):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件 {config_file} 不存在，使用默认配置")
        return {
            "server": {"ip": "81.71.152.21", "port": 31000},
            "audio": {"sample_rate": 16000, "channels": 1, "chunk_size": 512},
            "network": {"max_udp_size": 65507, "timeout": 5.0},
            "ui": {"window_title": "反作弊语音客户端", "window_size": "600x500"},
            "logging": {"level": "INFO", "file": "logs/client.log", "console": True}
        }
    except json.JSONDecodeError as e:
        print(f"配置文件格式错误: {e}")
        return load_config()  # 返回默认配置

# 加载配置
CONFIG = load_config()

class GUIClient:
    def __init__(self, config=None):
        if config is None:
            config = CONFIG

        # 服务器配置
        self.server = (config["server"]["ip"], config["server"]["port"])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 绑定到固定源端口，避免Windows动态分配端口导致频繁变化
        try:
            # 方法1：使用connect建立UDP"连接"，固定源端口
            self.sock.connect(self.server)
            # 获取实际绑定的本地端口
            local_addr = self.sock.getsockname()
            print(f"🔌 UDP客户端绑定到固定端口: {local_addr}")
        except Exception as e:
            print(f"⚠️ UDP端口绑定失败: {e}")
            # 回退到传统方式
            pass

        # 音频配置
        self.sample_rate = config["audio"]["sample_rate"]
        self.channels = config["audio"]["channels"]
        self.chunk_size = config["audio"]["chunk_size"]

        # 网络配置
        self.max_udp_size = config["network"]["max_udp_size"]
        self.timeout = config["network"]["timeout"]

        # UI配置
        self.window_title = config["ui"]["window_title"]
        self.window_size = config["ui"]["window_size"]

        self.codec = ADPCMCodec()
        self.running = False
        self.stream = None
        self.log_queue = queue.Queue()
        # 简单聚合器：短时间内到达的多个MP3片段合并后再播，避免乱序
        self._agg_chunks = []
        self._agg_last_time = 0.0

        # 分包重组状态管理
        self.fragment_buffers = {}  # {(session_id, chunk_id): {fragments: {}, total: int, start_time: float}}

        # 音频播放队列（新增）
        self.audio_queue = AudioPlayQueue(max_size=5)
        self.audio_queue.set_log_callback(self.log)

        # WebSocket信令客户端（新增）
        self.interrupt_client = InterruptSignalClient(
            server_host=self.server[0],  # 使用UDP服务器的IP
            server_port=31004            # WebSocket端口
        )
        self.interrupt_client.set_log_callback(self.log)
        self.interrupt_client.set_interrupt_callback(self._handle_interrupt_signal)
        self.interrupt_client.set_start_session_callback(self._handle_start_session_signal)

        # WebSocket连接状态
        self.websocket_started = False

        # 日志到文件
        log_dir = os.path.dirname(config["logging"]["file"])
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(filename=config["logging"]["file"],
                            level=getattr(logging, config["logging"]["level"]),
                            format='%(asctime)s %(levelname)s %(message)s')

        # 接收线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

    def log(self, msg: str):
        print(msg)
        logging.info(msg)
        self.log_queue.put(msg)

    def _recv_loop(self):
        backoff = 0.1
        while True:
            try:
                self.sock.settimeout(2.0)
                pkt, server_addr = self.sock.recvfrom(self.max_udp_size)

                # 启动WebSocket连接（仅第一次）
                if not self.websocket_started:
                    self._start_websocket_connection()
                    self.websocket_started = True

                # 尝试解析新格式（带session和chunk ID，支持分包）
                try:
                    t, session_id, chunk_id, fragment_index, total_fragments, payload = ADPCMProtocol.unpack_audio_with_session(pkt)
                    if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                        if total_fragments == 1:
                            # 单包，放入播放队列
                            self.log(f"📦 收到音频: session={session_id}, chunk={chunk_id}, 大小={len(payload)}字节")
                            self._add_audio_to_queue(session_id, chunk_id, payload)
                        else:
                            # 分包，需要重组
                            self.log(f"📦 收到分包: session={session_id}, chunk={chunk_id}, 分包={fragment_index+1}/{total_fragments}, 大小={len(payload)}字节")
                            self.log(f"🔍 分包详情: fragment_index={fragment_index}, total_fragments={total_fragments}")
                            self._handle_fragmented_audio(session_id, chunk_id, fragment_index, total_fragments, payload)
                        backoff = 0.1
                        continue
                except (ValueError, struct.error):
                    # 新格式解析失败，尝试旧格式
                    pass

                # 回退到旧格式处理
                t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                    self.log(f"📦 收到旧格式音频，大小={len(payload)}字节")
                    # 兼容旧的分片逻辑（保留用于向后兼容）
                    now = time.time()
                    if len(payload) >= 4:
                        total, idx = struct.unpack('!HH', payload[:4])
                        # 合法分片范围（1..200），否则当作无分片
                        if 1 <= total <= 200 and 1 <= idx <= total:
                            data = payload[4:]
                            # 初始化/复用分片状态
                            state = getattr(self, '_frag_state', None)
                            if not state or (state.get('total', 0) != total) or (now - state.get('start', 0) > 3.0):
                                state = {'total': total, 'parts': {}, 'start': now}
                                self._frag_state = state
                            # 写入分片（不清空旧分片，防止先到2/2后到1/2被清空）
                            state['parts'][idx] = data
                            self.log(f"📥 分片 {idx}/{total} 到达，已收 {len(state['parts'])}/{total}")
                            # 如果收齐，按序合并播放
                            if len(state['parts']) == total and total > 1:
                                ordered = b"".join(state['parts'][i] for i in range(1, total+1))
                                self.log(f"🎵 分片齐全，合并播放，总大小:{len(ordered)}")
                                self._play_mp3_bytes(ordered)
                                self._frag_state = None
                            # 单片总数=1的情况
                            if total == 1:
                                self._play_mp3_bytes(data)
                            continue
                    # 无分片头或不合法：直接当作完整MP3播放
                    self._play_mp3_bytes(payload)
                backoff = 0.1
            except socket.timeout:
                # 静音时没有回复是正常的
                pass
            except Exception as e:
                self.log(f"client recv error: {e}")
                self.log(f"🔍 数据包大小: {len(pkt) if 'pkt' in locals() else 'N/A'} 字节")
                if 'pkt' in locals() and len(pkt) > 0:
                    self.log(f"🔍 数据包前16字节: {pkt[:16].hex() if len(pkt) >= 16 else pkt.hex()}")
                    self.log(f"🔍 数据包类型: {type(pkt)}")
                import traceback
                self.log(f"🔍 详细错误: {traceback.format_exc()}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)

    def _handle_fragmented_audio(self, session_id: str, chunk_id: int,
                               fragment_index: int, total_fragments: int, fragment_data: bytes):
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
                'total': total_fragments,
                'start_time': now
            }

        buffer_info = self.fragment_buffers[key]

        # 检查分包总数是否一致
        if buffer_info['total'] != total_fragments:
            self.log(f"⚠️ 分包总数不一致，重置缓存: session={session_id}, chunk={chunk_id}")
            buffer_info = {
                'fragments': {},
                'total': total_fragments,
                'start_time': now
            }
            self.fragment_buffers[key] = buffer_info

        # 存储分包数据
        buffer_info['fragments'][fragment_index] = fragment_data
        received_count = len(buffer_info['fragments'])

        self.log(f"📥 分包缓存: session={session_id}, chunk={chunk_id}, 已收={received_count}/{total_fragments}")

        # 检查是否收齐所有分包
        if received_count == total_fragments:
            # 按顺序重组数据
            complete_data = b""
            for i in range(total_fragments):
                if i in buffer_info['fragments']:
                    complete_data += buffer_info['fragments'][i]
                else:
                    self.log(f"❌ 分包{i}缺失，无法重组: session={session_id}, chunk={chunk_id}")
                    return

            # 清理缓存
            del self.fragment_buffers[key]

            # 将重组后的音频放入播放队列
            self.log(f"🎵 分包重组完成，放入播放队列: session={session_id}, chunk={chunk_id}, 总大小={len(complete_data)}字节")
            self._add_audio_to_queue(session_id, chunk_id, complete_data)

    def _add_audio_to_queue(self, session_id: str, chunk_id: int, audio_data: bytes):
        """将音频数据添加到播放队列"""
        # 检查是否是新的session
        if session_id != self.audio_queue.current_session:
            self.audio_queue.start_new_session(session_id)

        # 创建AudioChunk并添加到队列
        chunk = AudioChunk(
            data=audio_data,
            session_id=session_id,
            chunk_id=chunk_id,
            timestamp=time.time()
        )

        success = self.audio_queue.add_chunk(chunk)
        if not success:
            self.log(f"⚠️ 音频chunk添加失败: session={session_id}, chunk={chunk_id}")

    def _handle_interrupt_signal(self, session_id: str, interrupt_after_chunk: int):
        """处理打断信号"""
        self.log(f"🛑 处理打断信号: session={session_id}, interrupt_after_chunk={interrupt_after_chunk}")

        # 设置音频队列的打断水位线
        self.audio_queue.set_interrupt_watermark(session_id, interrupt_after_chunk)

    def _handle_start_session_signal(self, session_id: str):
        """处理新session开始信号"""
        self.log(f"🎵 处理新session信号: session={session_id}")

        # 启动新的播放session
        self.audio_queue.start_new_session(session_id)

    def _start_websocket_connection(self):
        """启动WebSocket连接"""
        try:
            # 使用服务器地址作为标识，服务器会用实际收到UDP包的地址来绑定
            # 这样避免了客户端地址获取的复杂性
            server_ip = self.server[0]
            server_port = self.server[1]

            self.log(f"🔗 启动WebSocket连接，目标服务器: {server_ip}:{server_port}")
            self.interrupt_client.start(server_ip, server_port)

        except Exception as e:
            self.log(f"⚠️ WebSocket连接启动失败: {e}")

    def _play_mp3_bytes(self, audio_bytes: bytes):
        self.log(f"🔊 开始播放MP3，大小: {len(audio_bytes)} 字节")
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()  # 确保数据写入磁盘
                path = tmp.name

            self.log(f"📁 临时文件创建: {path}")

            try:
                import pygame

                # 重新初始化mixer，确保干净状态
                if pygame.mixer.get_init():
                    pygame.mixer.quit()

                # 初始化音频系统
                pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
                pygame.mixer.init()
                self.log("🎵 pygame mixer 初始化成功")

                # 加载并播放
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self.log("▶️ 开始播放音频...")

                # 等待播放完成，同时检查打断事件
                play_start = time.time()
                while pygame.mixer.music.get_busy():
                    if self.audio_queue.is_interrupted():
                        self.log("🛑 检测到打断事件，立即停止播放")
                        pygame.mixer.music.stop()
                        self.audio_queue.clear_interrupt()  # 清除打断事件
                        break
                    time.sleep(0.1)
                    # 防止无限等待
                    if time.time() - play_start > 30:
                        self.log("⚠️ 播放超时，强制停止")
                        pygame.mixer.music.stop()
                        break

                self.log("✅ 音频播放完成")

                # 确保pygame完全释放文件
                pygame.mixer.music.unload()
                time.sleep(0.1)  # 给系统一点时间释放文件句柄

            except Exception as e:
                self.log(f"❌ pygame播放错误: {e}")
                # 尝试备用播放方法
                self._try_alternative_play(path)

            finally:
                # 清理临时文件
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                        self.log(f"🗑️ 临时文件已删除: {path}")
                except Exception as e:
                    self.log(f"⚠️ 删除临时文件失败: {e}")

        except Exception as e:
            self.log(f"❌ MP3播放总体错误: {e}")
            import traceback
            self.log(f"详细错误: {traceback.format_exc()}")

    def _try_alternative_play(self, file_path):
        """备用播放方法"""
        try:
            import subprocess
            import platform

            system = platform.system().lower()
            self.log(f"🔄 尝试系统播放器，系统: {system}")

            if system == "windows":
                # Windows: 使用系统默认播放器
                os.startfile(file_path)
                self.log("🎵 使用Windows默认播放器")
            elif system == "darwin":  # macOS
                subprocess.run(["afplay", file_path], check=True)
                self.log("🎵 使用macOS afplay")
            else:  # Linux
                # 尝试多个Linux播放器
                players = ["mpg123", "mplayer", "vlc", "paplay"]
                for player in players:
                    try:
                        subprocess.run([player, file_path], check=True, timeout=30)
                        self.log(f"🎵 使用{player}播放成功")
                        return
                    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                self.log("❌ 所有备用播放器都失败")

        except Exception as e:
            self.log(f"❌ 备用播放方法失败: {e}")

    def _is_complete_mp3(self, data: bytes) -> bool:
        """检查是否是完整的 MP3 文件（非常宽松）"""
        if len(data) < 50:  # 至少50字节
            return False

        # 检查 MP3 头部标识
        has_id3 = data[:3] == b'ID3'
        has_mp3_frame = data[:2] == b'\xff\xfb' or data[:2] == b'\xff\xfa'

        # 非常宽松的检测条件
        if has_id3 or has_mp3_frame:
            # 如果有MP3标识且数据大于500字节，就认为可以播放
            if len(data) > 500:  # 进一步降低到500字节
                self.log(f"✅ MP3可播放: {len(data)} 字节 ({'ID3' if has_id3 else 'MP3帧'})")
                return True

        # 如果数据超过5KB，强制播放（大幅降低阈值）
        if len(data) > 5000:
            self.log(f"✅ 强制播放: {len(data)} 字节")
            return True

        # 如果数据看起来像音频数据，也尝试播放
        if len(data) > 1000 and (b'LAME' in data or b'Xing' in data):
            self.log(f"✅ 检测到音频编码器标识: {len(data)} 字节")
            return True

        return False

    def _try_play_buffered_mp3(self):
        """尝试播放缓冲区中的 MP3（超时机制）"""
        if len(self.mp3_buffer) > 1000:  # 至少1KB才播放
            current_time = time.time()
            # 如果距离最后一个片段超过 1.5 秒，播放缓冲的内容
            if current_time - self.last_mp3_time >= 1.5:
                self.log(f"⏰ 超时播放缓冲MP3: {len(self.mp3_buffer)} 字节")
                self._play_mp3_bytes(self.mp3_buffer)
                self.mp3_buffer = b""
            else:
                # 继续等待
                threading.Timer(0.5, self._try_play_buffered_mp3).start()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.log(f"🎤 音频状态: {status}")

        block = indata.flatten().astype(np.float32)

        # 检测音频强度（减少日志）
        volume = np.sqrt(np.mean(block**2))

        try:
            compressed = self.codec.encode(block)
            pkt = ADPCMProtocol.pack_audio_packet(compressed, ADPCMProtocol.COMPRESSION_ADPCM)

            # 调试：检查数据包大小
            if len(pkt) > 1400:
                self.log(f"⚠️ 上行数据包过大: {len(pkt)} 字节，可能被截断")

            # 使用send()而不是sendto()，因为socket已经connect到服务器
            try:
                self.sock.send(pkt)
            except OSError:
                # 如果connect失败，回退到sendto方式
                self.sock.sendto(pkt, self.server)

            # 减少日志频率
            if hasattr(self, '_send_count'):
                self._send_count += 1
            else:
                self._send_count = 1

            # 只在有声音且每500个包时记录一次
            if volume > 0.02 and self._send_count % 500 == 0:
                self.log(f"🎤 音频活跃，已发送 {self._send_count} 包")

        except Exception as e:
            self.log(f"❌ 音频发送失败: {e}")

    def start_stream(self):
        if self.running:
            return
        try:
            # 发送连接信号，触发服务器发送开场白
            hello_pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_HELLO)
            try:
                self.sock.send(hello_pkt)
            except OSError:
                # 如果connect失败，回退到sendto方式
                self.sock.sendto(hello_pkt, self.server)

            self.stream = sd.InputStream(
                dtype='float32',
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
            self.stream.start()
            self.running = True

            self.log("🎙️ 已开始采集，等待开场白...")
            self.log("🔗 WebSocket将在收到第一个音频包后启动...")
        except Exception as e:
            self.log(f"audio stream error: {e}")

    def reset_session(self):
        try:
            pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_RESET)
            try:
                self.sock.send(pkt)
            except OSError:
                # 如果connect失败，回退到sendto方式
                self.sock.sendto(pkt, self.server)
            # 客户端本地也清一下编码状态，视觉上更干净
            self.codec.reset_all()
            self.log("🧹 已请求服务器重置会话（提示词级）")
        except Exception as e:
            self.log(f"reset error: {e}")

    def close(self):
        try:
            # 停止音频播放队列
            self.audio_queue.stop()

            # 停止WebSocket信令客户端
            self.interrupt_client.stop()

            if self.stream:
                self.stream.stop(); self.stream.close()
        except:
            pass
        try:
            self.sock.close()
        except:
            pass


def run_gui():
    app = GUIClient()

    root = Tk()
    root.title(app.window_title)
    root.geometry(app.window_size)

    # 设置窗口图标（可选）
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'app.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    txt = Text(root, height=12, width=56)
    txt.pack(pady=10)

    def pump_logs():
        while not app.log_queue.empty():
            line = app.log_queue.get()
            txt.configure(state=NORMAL)
            txt.insert(END, line + "\n")
            txt.see(END)
            txt.configure(state=DISABLED)
        root.after(100, pump_logs)

    # 优先使用图标按钮；无图标时回退文字
    try:
        assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        start_png = os.path.join(assets_dir, 'start.png')
        reset_png = os.path.join(assets_dir, 'reset.png')
        if os.path.exists(start_png) and os.path.exists(reset_png):
            start_img = PhotoImage(file=start_png)
            reset_img = PhotoImage(file=reset_png)
            btn_start = Button(root, image=start_img, command=app.start_stream)
            btn_start.image = start_img  # 防止被回收
            btn_reset = Button(root, image=reset_img, command=app.reset_session)
            btn_reset.image = reset_img
        else:
            raise FileNotFoundError
    except Exception:
        btn_start = Button(root, text="开始", command=app.start_stream)
        btn_reset = Button(root, text="重置", command=app.reset_session)

    btn_start.pack(side='left', padx=30)
    btn_reset.pack(side='right', padx=30)

    def on_close():
        app.close(); root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    pump_logs()
    app.recv_thread.start()
    root.mainloop()

if __name__ == "__main__":
    run_gui()

