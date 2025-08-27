#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小改动 UDP 服务器（多客户端）
- 上行：ADPCM（float32/16kHz/mono/512块编码）→ 解码为 float32 块 → 投喂现有管线
- 下行：真实 Edge TTS 生成 MP3 → UDP 回发（一次性）
"""

import socket
import threading
import queue
import time
from typing import Dict, Tuple

import numpy as np
import struct

import whisper.config as config
from adpcm_codec import ADPCMCodec, ADPCMProtocol
from whisper.vad_module import VADModule
from whisper.audio_handler import AudioHandler
from whisper.transcriber_module import Transcriber
import os
import sys
# 确保可以导入 whisper 目录下的现有模块（config/vad_module 等）
WHISPER_DIR = os.path.join(os.path.dirname(__file__), 'whisper')
if WHISPER_DIR not in sys.path:
    sys.path.insert(0, WHISPER_DIR)

from whisper.brain_ai_module import KimiAI
from websocket_signal import InterruptSignalServer
from tts_module_udp_adapter import TTSModuleUDPAdapter

UDP_PORT = 31000
MAX_UDP = 65507

class UDPVoiceServer:
    def __init__(self, host: str = "0.0.0.0", port: int = UDP_PORT):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 设置端口重用选项，避免"Address already in use"错误
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind(self.addr)
        except OSError as e:
            if e.errno == 98:  # Address already in use
                print(f"❌ 端口 {port} 被占用，尝试自动清理...")
                self._kill_existing_process(port)
                # 重试绑定
                try:
                    self.sock.bind(self.addr)
                    print(f"✅ 端口清理成功，服务器绑定到 {self.addr}")
                except OSError:
                    print(f"❌ 无法绑定端口 {port}，请手动清理:")
                    print(f"   sudo lsof -ti:{port} | xargs kill -9")
                    raise
            else:
                raise

        self.running = True

        # 初始化数据结构与模块（确保即使未调用清理函数也已就绪）
        self.client_codecs: Dict[Tuple[str,int], ADPCMCodec] = {}
        self.client_queues: Dict[Tuple[str,int], queue.Queue] = {}
        self.client_handlers: Dict[Tuple[str,int], AudioHandler] = {}
        self.client_ai: Dict[Tuple[str,int], KimiAI] = {}

        # 共享模块
        self.vad = VADModule(config.VAD_SENSITIVITY)
        self.transcriber = Transcriber(config.WHISPER_MODEL_SIZE, config.DEVICE)
        self.tts_udp = TTSModuleUDPAdapter()

        # 处理线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.proc_thread = threading.Thread(target=self._process_loop, daemon=True)

        # 会话管理
        self.client_last_activity = {}
        self.client_welcomed = set()  # 存储已欢迎的IP
        self.client_welcome_time = {}  # 存储欢迎时间，防止重复欢迎

        # Session和Chunk管理 (新增)
        self.client_sessions: Dict[Tuple[str,int], str] = {}      # {addr: current_session_id}
        self.client_chunk_counters: Dict[Tuple[str,int], int] = {} # {addr: chunk_counter}
        self.client_interrupt_cooldown: Dict[Tuple[str,int], float] = {} # {addr: next_allowed_time}

        # 分片重组缓存 (新增)
        self.fragment_cache = {}  # {addr: {key: fragment_data}}

        # 线程安全锁 (新增)
        self.interrupt_lock = threading.Lock()  # 打断状态锁
        self.session_lock = threading.Lock()    # Session状态锁

        # 统一状态管理 (新增)
        self.client_states = {}  # {addr: {active_session, current_chunk, interrupt_cooldown, last_interrupt_time}}

        # 智能打断配置 (新增)
        self.INTERRUPT_COOLDOWN = 2.0  # 成功打断后的冷却
        self.ATTEMPT_COOLDOWN = 0.3    # 尝试打断后的短冷却
        self.MIN_INTERRUPT_LENGTH = 2  # 最小有效长度

        # 语气词黑名单 (新增)
        self.FILLER_WORDS = {
            # 中文语气词
            '嗯', '啊', '呃', '额', '哦', '唔', '嗯嗯', '啊啊', '呃呃',
            '那个', '这个', '就是', '然后', '嗯哼', '哼', '咳',
            # 英文语气词
            'um', 'uh', 'er', 'ah', 'oh', 'hmm', 'well', 'like', 'you know',
            # 常见噪音词
            '咳咳', '清嗓', '嘘', '咦', '诶', '哎', '唉'
        }

        # 打断功能控制 (新增)
        self.interrupt_enabled = True  # 全局打断开关

        # WebSocket地址映射 (新增)
        self.websocket_address_map = {}  # {server_addr: actual_client_addr}

        # WebSocket信令服务器 (新增)
        self.interrupt_server = InterruptSignalServer(host="0.0.0.0", port=31004)
        self.interrupt_server.set_log_callback(self._log_websocket)

    def _kill_existing_process(self, port: int):
        """尝试杀死占用指定端口的进程"""
        import subprocess
        try:
            # 查找占用端口的进程
            result = subprocess.run(['lsof', '-ti', f':{port}'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        print(f"🎯 杀死进程 PID: {pid}")
                        subprocess.run(['kill', '-9', pid], timeout=5)
                time.sleep(1)  # 等待进程完全退出
            else:
                # 备用方法：杀死所有相关Python进程
                subprocess.run(['pkill', '-9', '-f', 'simple_udp_server.py'], timeout=5)
                time.sleep(1)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"⚠️ 自动清理失败: {e}")
            print("请手动执行: sudo lsof -ti:31000 | xargs kill -9")

        # 多客户端：为每个客户端维护独立的编解码状态、缓冲队列与会话上下文
        self.client_codecs: Dict[Tuple[str,int], ADPCMCodec] = {}
        self.client_queues: Dict[Tuple[str,int], queue.Queue] = {}
        self.client_handlers: Dict[Tuple[str,int], AudioHandler] = {}
        self.client_ai: Dict[Tuple[str,int], KimiAI] = {}

        # 共享模块（与 main.py 对齐）
        self.vad = VADModule(config.VAD_SENSITIVITY)
        self.transcriber = Transcriber(config.WHISPER_MODEL_SIZE, config.DEVICE)
        self.tts_udp = TTSModuleUDPAdapter()

        # 处理线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.proc_thread = threading.Thread(target=self._process_loop, daemon=True)

        # 会话管理
        self.client_last_activity = {}  # 记录客户端最后活动时间
        self.client_welcomed = set()  # 记录已发送开场白的客户端
        self.client_welcomed = set()  # 记录已发送开场白的客户端

    def start(self):
        self.running = True

        # 启动WebSocket信令服务器
        self.interrupt_server.start()

        print(f"UDPVoiceServer listening on {self.addr}")
        self.recv_thread.start()
        self.proc_thread.start()

    def stop(self):
        self.running = False

        # 停止WebSocket信令服务器
        self.interrupt_server.stop()

        self.sock.close()

    def _log_websocket(self, message: str):
        """WebSocket信令服务器日志回调"""
        print(f"[WebSocket] {message}")

    def _get_client_state(self, addr: Tuple[str,int]) -> dict:
        """获取客户端状态（线程安全）"""
        with self.session_lock:
            if addr not in self.client_states:
                self.client_states[addr] = {
                    'active_session': '',
                    'current_chunk': 0,
                    'interrupt_cooldown': 0.0,
                    'last_interrupt_time': 0.0
                }
            return self.client_states[addr].copy()  # 返回副本避免外部修改

    def _update_client_chunk(self, addr: Tuple[str,int], session_id: str, chunk_id: int):
        """更新客户端chunk状态（线程安全）"""
        with self.interrupt_lock:  # 使用打断锁保护
            with self.session_lock:
                if addr not in self.client_states:
                    self.client_states[addr] = {
                        'active_session': '',
                        'current_chunk': 0,
                        'interrupt_cooldown': 0.0,
                        'last_interrupt_time': 0.0
                    }

                self.client_states[addr]['active_session'] = session_id
                self.client_states[addr]['current_chunk'] = chunk_id

                print(f"🔄 状态更新: addr={addr}, session={session_id}, chunk={chunk_id}")

    def _is_valid_interrupt_text(self, transcription: str) -> bool:
        """检查转写文本是否值得触发打断"""
        if not transcription:
            return False

        # 清理文本
        text = transcription.strip().lower()

        # 长度检查
        if len(text) < self.MIN_INTERRUPT_LENGTH:
            print(f"🚫 文本太短，不触发打断: '{text}'")
            return False

        # 语气词检查
        if text in self.FILLER_WORDS:
            print(f"🚫 语气词过滤，不触发打断: '{text}'")
            return False

        # 组合语气词检查（多个语气词组合）
        words = text.split()
        if len(words) <= 3 and all(word in self.FILLER_WORDS for word in words):
            print(f"🚫 组合语气词过滤，不触发打断: '{text}'")
            return False

        # 重复字符检查（如"啊啊啊啊"），但排除有意义的重复词
        meaningful_repeats = {'喂喂', '喂喂喂', '你好你好', 'hello', 'hellohi'}
        if (len(set(text.replace(' ', ''))) <= 2 and len(text) >= 3 and
            text not in meaningful_repeats):
            print(f"🚫 重复字符过滤，不触发打断: '{text}'")
            return False

        print(f"✅ 有效打断文本: '{text}'")
        return True

    def _set_interrupt_cooldown(self, addr: Tuple[str,int], successful_interrupt: bool):
        """设置智能冷却时间"""
        now = time.time()

        if successful_interrupt:
            # 成功打断：长冷却
            cooldown_time = now + self.INTERRUPT_COOLDOWN
            cooldown_type = "成功打断"
        else:
            # 尝试打断但被过滤：短冷却
            cooldown_time = now + self.ATTEMPT_COOLDOWN
            cooldown_type = "尝试打断"

        with self.session_lock:
            if addr not in self.client_states:
                self.client_states[addr] = {
                    'active_session': '',
                    'current_chunk': 0,
                    'interrupt_cooldown': 0.0,
                    'last_interrupt_time': 0.0
                }
            self.client_states[addr]['interrupt_cooldown'] = cooldown_time

        print(f"⏰ 设置{cooldown_type}冷却: {cooldown_time - now:.1f}秒")

    def _update_websocket_binding(self, actual_addr: Tuple[str,int]):
        """更新WebSocket地址绑定"""
        # 检查实际客户端地址是否已经绑定
        if self.interrupt_server.bind_udp_address(actual_addr):
            # 已经绑定了，不需要更新
            return

        # 查找是否有服务器地址的绑定需要更新
        server_addr = (self.addr[0] if self.addr[0] != '0.0.0.0' else '81.71.152.21', self.addr[1])

        if self.interrupt_server.bind_udp_address(server_addr):
            # 更新绑定到实际客户端地址
            success = self.interrupt_server.update_udp_binding(server_addr, actual_addr)
            if success:
                print(f"🔄 WebSocket绑定已更新: {server_addr} -> {actual_addr}")
            else:
                print(f"⚠️ WebSocket绑定更新失败: {server_addr} -> {actual_addr}")
        # 如果都没找到，说明WebSocket还没连接，这是正常的

    def _atomic_interrupt_check_and_trigger(self, addr: Tuple[str,int], transcription: str) -> bool:
        """原子化的打断检查和触发"""
        # 全局打断开关检查
        if not self.interrupt_enabled:
            print("🚫 打断功能已禁用（WebSocket不可用），继续正常对话")
            return False

        with self.interrupt_lock:  # 整个操作在锁内完成
            # 1. 原子化读取当前状态
            client_state = self._get_client_state(addr)
            current_session = client_state['active_session']
            current_chunk = client_state['current_chunk']
            cooldown_until = client_state['interrupt_cooldown']

            # 2. 检查打断条件
            now = time.time()

            # 检查冷却时间
            if now < cooldown_until:
                remaining = cooldown_until - now
                print(f"⏰ 打断冷却中，剩余 {remaining:.1f}秒")
                return False

            # 检查转写结果（加入语气词过滤）
            if not self._is_valid_interrupt_text(transcription):
                # 设置短冷却，避免频繁的无效尝试
                self._set_interrupt_cooldown(addr, successful_interrupt=False)
                return False

            # 检查是否有活跃session
            if not current_session:
                print(f"🚫 无活跃session，不触发打断")
                return False

            # 检查WebSocket连接（直接使用实际客户端地址）
            if not self.interrupt_server.bind_udp_address(addr):
                print(f"⚠️ WebSocket未连接，跳过打断: {addr}")
                return False

            # 3. 原子化执行打断
            print(f"🛑 原子化打断: session={current_session}, chunk={current_chunk}, text='{transcription}'")

            try:
                # 发送打断信号（使用当前读取的状态）
                success = self.interrupt_server.send_interrupt_signal(addr, current_session, current_chunk)
                if not success:
                    print(f"⚠️ 打断信号发送失败，客户端 {addr} 将继续播放")
                    return False

                # 原子化更新状态（不生成新session，继续使用当前session）
                with self.session_lock:
                    self.client_states[addr].update({
                        'interrupt_cooldown': now + self.INTERRUPT_COOLDOWN,
                        'last_interrupt_time': now
                    })
                    # 注意：不更新active_session，保持当前session继续对话
                    # 注意：不重置chunk计数器，让chunk编号继续递增

                print(f"✅ 打断完成: session={current_session}, chunk={current_chunk}")
                print(f"🛑 打断水位线: chunk={current_chunk}, 冷却到={now + self.INTERRUPT_COOLDOWN}")

                return True

            except Exception as e:
                print(f"❌ 打断执行失败: {e}")
                return False

    def _get_client_codec(self, addr: Tuple[str,int]) -> ADPCMCodec:
        if addr not in self.client_codecs:
            self.client_codecs[addr] = ADPCMCodec()
        return self.client_codecs[addr]

    def _get_client_queue(self, addr: Tuple[str,int]) -> queue.Queue:
        if addr not in self.client_queues:
            self.client_queues[addr] = queue.Queue(maxsize=1000)
        return self.client_queues[addr]

    def _get_client_handler(self, addr: Tuple[str,int]) -> AudioHandler:
        if addr not in self.client_handlers:
            self.client_handlers[addr] = AudioHandler(
                config.SILENCE_CHUNKS, config.MAX_SPEECH_S, config.AUDIO_SAMPLE_RATE
            )
        return self.client_handlers[addr]

    def _get_client_ai(self, addr: Tuple[str,int]) -> KimiAI:
        if addr not in self.client_ai:
            self.client_ai[addr] = KimiAI()
        return self.client_ai[addr]

    # === Session和Chunk管理方法 (新增) ===
    def generate_new_session_id(self, addr: Tuple[str,int]) -> str:
        """为客户端生成新的session ID"""
        import uuid
        session_id = str(uuid.uuid4())[:8]  # 8位短ID
        self.client_sessions[addr] = session_id
        self.client_chunk_counters[addr] = 0  # 重置chunk计数器
        print(f"🆔 为客户端 {addr} 生成新session: {session_id}")
        return session_id

    def get_current_session_id(self, addr: Tuple[str,int]) -> str:
        """获取客户端当前的session ID"""
        return self.client_sessions.get(addr, "")

    def get_next_chunk_id(self, addr: Tuple[str,int]) -> int:
        """获取客户端下一个chunk ID"""
        if addr not in self.client_chunk_counters:
            self.client_chunk_counters[addr] = 0
        self.client_chunk_counters[addr] += 1
        return self.client_chunk_counters[addr]

    def get_current_chunk_id(self, addr: Tuple[str,int]) -> int:
        """获取客户端当前的chunk ID"""
        return self.client_chunk_counters.get(addr, 0)

    # === 分片重组管理 (新增) ===
    def _handle_fragmented_audio(self, addr: Tuple[str,int], session_id: str, chunk_id: int,
                               fragment_index: int, total_fragments: int, fragment_data: bytes):
        """处理分包音频数据的重组（服务器端）"""
        key = (session_id, chunk_id)
        now = time.time()

        # 初始化客户端分片缓存
        if addr not in self.fragment_cache:
            self.fragment_cache[addr] = {}

        # 清理超时的分包缓存（超过5秒）
        expired_keys = []
        for cache_key, cache_data in self.fragment_cache[addr].items():
            if now - cache_data.get('timestamp', 0) > 5.0:
                expired_keys.append(cache_key)

        for expired_key in expired_keys:
            del self.fragment_cache[addr][expired_key]
            print(f"🗑️ 清理超时分包: {expired_key}")

        # 初始化或获取分包数据
        if key not in self.fragment_cache[addr]:
            self.fragment_cache[addr][key] = {
                'fragments': {},
                'total_fragments': total_fragments,
                'timestamp': now
            }

        # 存储分包数据
        cache_data = self.fragment_cache[addr][key]
        cache_data['fragments'][fragment_index] = fragment_data
        cache_data['timestamp'] = now  # 更新时间戳

        print(f"📥 收到分包: session={session_id}, chunk={chunk_id}, 分包={fragment_index+1}/{total_fragments}, 已收={len(cache_data['fragments'])}/{total_fragments}")

        # 检查是否收齐所有分包
        if len(cache_data['fragments']) == total_fragments:
            # 按顺序重组数据
            complete_data = b''
            for i in range(total_fragments):
                if i in cache_data['fragments']:
                    complete_data += cache_data['fragments'][i]
                else:
                    print(f"❌ 分包 {i} 缺失，重组失败")
                    return None

            # 清理缓存
            del self.fragment_cache[addr][key]
            print(f"✅ 分包重组完成: session={session_id}, chunk={chunk_id}, 总大小={len(complete_data)}字节")
            return complete_data

        return None  # 还未收齐

    # === 打断冷却管理 (新增) ===
    def can_interrupt(self, addr: Tuple[str,int]) -> bool:
        """检查是否可以触发打断（2s冷却）"""
        now = time.time()
        return now >= self.client_interrupt_cooldown.get(addr, 0)

    def set_interrupt_cooldown(self, addr: Tuple[str,int]):
        """设置打断冷却时间（2秒）"""
        self.client_interrupt_cooldown[addr] = time.time() + 2.0
        print(f"⏰ 设置打断冷却，客户端 {addr}，2秒内不可再次打断")

    def _send_opening_statement(self, addr: Tuple[str,int]):
        """向新客户端发送开场白（使用新的session管理）"""
        try:
            print(f"为新客户端 {addr} 生成开场白...")

            # 为开场白生成新的session
            session_id = self.generate_new_session_id(addr)

            kimi = self._get_client_ai(addr)
            opening_stream = kimi.generate_opening_statement()

            # 切句合成，使用新的session发送方法
            seg_list = self.tts_udp.generate_mp3_segments_from_stream(opening_stream)
            if seg_list:
                print(f"开场白共 {len(seg_list)} 段，session={session_id}")
                self._send_audio_segments_with_session(addr, seg_list, session_id)
            else:
                # 兜底：整段发送
                mp3_bytes = self.tts_udp.generate_mp3_from_stream(opening_stream)
                if mp3_bytes:
                    chunk_id = self.get_next_chunk_id(addr)
                    self._send_mp3_with_session(addr, mp3_bytes, session_id, chunk_id)

        except Exception as e:
            print(f"开场白发送失败: {e}")

    def _send_mp3_safe(self, addr: Tuple[str,int], mp3_bytes: bytes):
        """安全发送 MP3（自动处理分片）"""
        session_id = self.get_current_session_id(addr)
        chunk_id = self.get_next_chunk_id(addr)

        # 检查 UDP 包大小限制（与新协议保持一致）
        MAX_UDP_PAYLOAD = 1400  # 安全的互联网MTU大小
        HEADER_SIZE = 21  # 协议头部大小
        max_payload = MAX_UDP_PAYLOAD - HEADER_SIZE  # 1379字节

        if len(mp3_bytes) > max_payload:
            print(f"⚠️ MP3 过大 ({len(mp3_bytes)} 字节)，分片发送...")
            self._send_mp3_with_session(addr, mp3_bytes, session_id, chunk_id)
        else:
            try:
                packet = ADPCMProtocol.pack_audio_with_session(
                    mp3_bytes, session_id, chunk_id, ADPCMProtocol.COMPRESSION_TTS_MP3,
                    fragment_index=0, total_fragments=1
                )
                self.sock.sendto(packet, addr)
                print(f"✅ 发送MP3 session={session_id}, chunk={chunk_id}, 大小={len(mp3_bytes)}字节 -> {addr}")

                # 更新客户端状态
                self._update_client_chunk(addr, session_id, chunk_id)
            except Exception as e:
                print(f"MP3 发送失败: {e}")



    def _send_large_mp3(self, addr: Tuple[str,int], mp3_bytes: bytes):
        """分片发送大的 MP3 文件（旧版本，保持兼容）"""
        import struct
        chunk_size = 1400  # 1.4KB 每片，与新方法统一
        total_chunks = (len(mp3_bytes) + chunk_size - 1) // chunk_size

        for i in range(total_chunks):
            start = i * chunk_size
            end = min(start + chunk_size, len(mp3_bytes))
            chunk = mp3_bytes[start:end]

            try:
                # 在负载前添加 4 字节的分片头: [uint16 总片数][uint16 当前序号(从1开始)]
                header = struct.pack('!HH', total_chunks, i + 1)
                payload = header + chunk
                down = ADPCMProtocol.pack_audio_packet(payload, ADPCMProtocol.COMPRESSION_TTS_MP3)
                self.sock.sendto(down, addr)
                print(f"发送片段 {i+1}/{total_chunks} 给 {addr}")
                time.sleep(0.01)  # 小延迟避免丢包
            except Exception as e:
                print(f"片段 {i+1} 发送失败: {e}")
                break

    # === 新增：支持Session和Chunk的音频发送方法 ===
    def _send_mp3_with_session(self, addr: Tuple[str,int], mp3_bytes: bytes,
                              session_id: str, chunk_id: int):
        """发送带session和chunk ID的MP3数据（支持自动分包）"""
        try:
            # UDP安全包大小限制（互联网环境MTU限制）
            MAX_UDP_PAYLOAD = 1400  # 安全的互联网MTU大小
            # 协议头部大小：1+4+8+4+2+2 = 21字节
            HEADER_SIZE = 21
            MAX_AUDIO_PER_PACKET = MAX_UDP_PAYLOAD - HEADER_SIZE  # 1379字节

            # 检查是否需要分包
            if len(mp3_bytes) <= MAX_AUDIO_PER_PACKET:
                # 单包发送
                packet = ADPCMProtocol.pack_audio_with_session(
                    mp3_bytes, session_id, chunk_id, ADPCMProtocol.COMPRESSION_TTS_MP3,
                    fragment_index=0, total_fragments=1
                )
                self.sock.sendto(packet, addr)
                print(f"✅ 发送MP3 session={session_id}, chunk={chunk_id}, 大小={len(mp3_bytes)}字节 -> {addr}")

                # 更新客户端状态（线程安全）
                self._update_client_chunk(addr, session_id, chunk_id)

                return True
            else:
                # 分包发送
                total_fragments = (len(mp3_bytes) + MAX_AUDIO_PER_PACKET - 1) // MAX_AUDIO_PER_PACKET
                print(f"📦 MP3过大({len(mp3_bytes)}字节)，分为{total_fragments}包发送，session={session_id}, chunk={chunk_id}")
                print(f"🔍 分包计算: 音频大小={len(mp3_bytes)}, 每包最大={MAX_AUDIO_PER_PACKET}, 总分包数={total_fragments}")

                for fragment_index in range(total_fragments):
                    start_pos = fragment_index * MAX_AUDIO_PER_PACKET
                    end_pos = min(start_pos + MAX_AUDIO_PER_PACKET, len(mp3_bytes))
                    fragment_data = mp3_bytes[start_pos:end_pos]

                    print(f"🔍 准备分包 {fragment_index}: start={start_pos}, end={end_pos}, 数据大小={len(fragment_data)}")

                    packet = ADPCMProtocol.pack_audio_with_session(
                        fragment_data, session_id, chunk_id, ADPCMProtocol.COMPRESSION_TTS_MP3,
                        fragment_index=fragment_index, total_fragments=total_fragments
                    )

                    print(f"🔍 分包协议: fragment_index={fragment_index}, total_fragments={total_fragments}")

                    self.sock.sendto(packet, addr)
                    print(f"✅ 发送分包 session={session_id}, chunk={chunk_id}, 分包={fragment_index+1}/{total_fragments}, 大小={len(fragment_data)}字节")

                    # 分包间小延迟，避免网络拥塞
                    time.sleep(0.01)

                print(f"📦 分包发送完成 session={session_id}, chunk={chunk_id}")

                # 更新客户端状态（线程安全）
                self._update_client_chunk(addr, session_id, chunk_id)

                return True

        except Exception as e:
            print(f"❌ 发送MP3失败 session={session_id}, chunk={chunk_id}: {e}")
            return False

    def _send_audio_segments_with_session(self, addr: Tuple[str,int],
                                        mp3_segments: list, session_id: str):
        """发送一系列MP3片段，每个片段都带session和递增的chunk ID"""
        if not mp3_segments:
            print(f"⚠️ 没有音频片段可发送，session={session_id}")
            return

        print(f"📤 开始发送 {len(mp3_segments)} 个音频片段，session={session_id}")

        for i, mp3_data in enumerate(mp3_segments, 1):
            chunk_id = self.get_next_chunk_id(addr)
            success = self._send_mp3_with_session(addr, mp3_data, session_id, chunk_id)

            if success:
                # 小延迟确保客户端按序接收
                time.sleep(0.1)
            else:
                print(f"❌ 片段 {i}/{len(mp3_segments)} 发送失败，停止发送")
                break

        print(f"📤 音频片段发送完成，session={session_id}")

    def reset_client_session(self, addr: Tuple[str,int]):
        """重置指定客户端的会话状态"""
        if addr in self.client_codecs:
            self.client_codecs[addr].reset_all()
            print(f"已重置客户端 {addr} 的 ADPCM 编解码状态")

        if addr in self.client_handlers:
            # AudioHandler 重置（清空缓冲区）
            handler = self.client_handlers[addr]
            handler.audio_buffer.clear()
            handler.is_recording = False
            print(f"已重置客户端 {addr} 的音频处理状态")

        if addr in self.client_ai:
            # 重置 AI 对话历史
            ai = self.client_ai[addr]
            ai.conversation_history.clear()
            print(f"已重置客户端 {addr} 的 AI 对话历史")

        # 清空队列
        if addr in self.client_queues:
            q = self.client_queues[addr]
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
            print(f"已清空客户端 {addr} 的音频队列")

        # 重置开场白标记，下次连接会重新发送
        self.client_welcomed.discard(addr)

        print(f"✅ 客户端 {addr} 会话完全重置")

    def cleanup_inactive_clients(self, timeout_seconds=300):
        """清理超时的客户端会话（5分钟无活动）"""
        current_time = time.time()
        inactive_clients = []

        for addr, last_time in self.client_last_activity.items():
            if current_time - last_time > timeout_seconds:
                inactive_clients.append(addr)

        for addr in inactive_clients:
            print(f"清理超时客户端: {addr}")
            self.reset_client_session(addr)
            # 删除记录
            self.client_last_activity.pop(addr, None)
            self.client_codecs.pop(addr, None)
            self.client_queues.pop(addr, None)
            self.client_handlers.pop(addr, None)
            self.client_ai.pop(addr, None)
            self.client_welcomed.discard(addr)

    def _recv_loop(self):
        while self.running:
            try:
                pkt, addr = self.sock.recvfrom(MAX_UDP)

                # 尝试解析新格式（带session和chunk ID，支持分包）
                try:
                    t, session_id, chunk_id, fragment_index, total_fragments, payload = ADPCMProtocol.unpack_audio_with_session(pkt)
                    if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                        if total_fragments == 1:
                            # 单包，直接处理
                            print(f"📦 收到音频: session={session_id}, chunk={chunk_id}, 大小={len(payload)}字节")
                            # 这里可以添加TTS音频处理逻辑
                        else:
                            # 分包，需要重组
                            complete_data = self._handle_fragmented_audio(addr, session_id, chunk_id, fragment_index, total_fragments, payload)
                            if complete_data:
                                print(f"📦 分包重组完成: session={session_id}, chunk={chunk_id}, 大小={len(complete_data)}字节")
                                # 这里可以添加重组后的TTS音频处理逻辑
                        continue
                    elif t == ADPCMProtocol.COMPRESSION_ADPCM:
                        # 新格式的ADPCM数据，直接处理
                        compression_type = t
                    else:
                        continue
                except (ValueError, struct.error):
                    # 新格式解析失败，尝试旧格式
                    compression_type, payload = ADPCMProtocol.unpack_audio_packet(pkt)

                if compression_type == ADPCMProtocol.COMPRESSION_ADPCM:
                    # 更新客户端活动时间
                    self.client_last_activity[addr] = time.time()

                    # 更新WebSocket地址绑定
                    self._update_websocket_binding(addr)

                    # 新客户端首次连接，立即发送开场白（基于IP判断，不考虑端口）
                    client_ip = addr[0]  # 只取IP部分
                    now = time.time()

                    if client_ip not in self.client_welcomed:
                        self.client_welcomed.add(client_ip)
                        self.client_welcome_time[client_ip] = now
                        print(f"🎉 新客户端IP首次连接: {client_ip}")
                        self._send_opening_statement(addr)
                    else:
                        # 检查是否需要重新发送欢迎语（超过5分钟）
                        last_welcome = self.client_welcome_time.get(client_ip, 0)
                        if now - last_welcome > 300:  # 5分钟
                            self.client_welcome_time[client_ip] = now
                            print(f"🔄 客户端长时间重连，重新发送欢迎语: {client_ip}")
                            self._send_opening_statement(addr)
                        else:
                            # 只在新端口时记录重连，避免刷屏
                            if addr not in self.client_last_activity or now - self.client_last_activity[addr] > 10:
                                print(f"🔄 客户端重连: {addr} (IP: {client_ip})")

                    codec = self._get_client_codec(addr)
                    try:
                        float_block = codec.decode(payload)  # float32 PCM ~512

                        # 检查解码结果
                        if len(float_block) == 0:
                            print(f"⚠️ ADPCM解码产生空块，payload大小: {len(payload)}")
                            continue
                        elif len(float_block) < 400:  # 放宽限制，400采样以上都接受
                            print(f"⚠️ ADPCM解码块太短: {len(float_block)} 采样，payload大小: {len(payload)}")
                            continue

                        q = self._get_client_queue(addr)
                        try:
                            q.put_nowait(float_block)
                        except queue.Full:
                            _ = q.get_nowait()
                            q.put_nowait(float_block)

                    except Exception as e:
                        print(f"❌ ADPCM解码失败: {e}, payload大小: {len(payload)}")
                elif compression_type == ADPCMProtocol.CONTROL_RESET:
                    self.reset_client_session(addr)
                elif compression_type == ADPCMProtocol.CONTROL_HELLO:
                    # 客户端连接信号，发送开场白
                    if addr not in self.client_welcomed:
                        self.client_welcomed.add(addr)
                        self._send_opening_statement(addr)
                else:
                    # 其他类型暂不处理
                    pass
            except Exception as e:
                print(f"recv_loop error: {e}")
                time.sleep(0.01)

    def _process_loop(self):
        """遍历所有客户端队列，按现有主逻辑处理，触发后下行 MP3"""
        while self.running:
            try:
                for addr, q in list(self.client_queues.items()):
                    # 拉取尽可能多的块（但不阻塞）
                    processed_any = False
                    while not q.empty():
                        float_block = q.get_nowait()
                        processed_any = True

                        # 检查音频块大小
                        if len(float_block) < 400:  # 放宽限制，400采样以上都接受
                            print(f"⚠️ 音频块太短: {len(float_block)} 采样，跳过处理")
                            continue

                        try:
                            # VAD需要固定512采样，如果不足则填充零
                            if len(float_block) < 512:
                                padded_block = np.zeros(512, dtype=np.float32)
                                padded_block[:len(float_block)] = float_block
                                is_speech = self.vad.is_speech(padded_block)
                            else:
                                is_speech = self.vad.is_speech(float_block)
                        except Exception as e:
                            print(f"❌ VAD处理失败: {e}, 音频块大小: {len(float_block)}")
                            continue

                        try:
                            handler = self._get_client_handler(addr)
                            # 音频处理器也可能需要固定大小，使用填充后的块
                            if len(float_block) < 512:
                                padded_block = np.zeros(512, dtype=np.float32)
                                padded_block[:len(float_block)] = float_block
                                triggered = handler.process_chunk(padded_block, is_speech)
                            else:
                                triggered = handler.process_chunk(float_block, is_speech)
                        except Exception as e:
                            print(f"❌ 音频处理失败: {e}, 音频块大小: {len(float_block)}")
                            continue
                        if triggered is not None:
                            print(f"客户端 {addr} 触发转写，音频长度: {len(triggered)} 采样")
                            # 触发：整段 audio → 真实链路（转写→LLM→TTS）
                            from whisper.prompts import WHISPER_PROMPT
                            text = self.transcriber.transcribe_audio(
                                triggered,
                                config.LANGUAGE_CODE,
                                initial_prompt=WHISPER_PROMPT
                            )
                            print(f"转写结果: {text}")
                            if text:
                                # 检查是否需要触发打断
                                interrupt_triggered = self._atomic_interrupt_check_and_trigger(addr, text)

                                if interrupt_triggered:
                                    print(f"🛑 已触发打断，继续当前session对话")

                                print(f"开始 AI 对话生成...")
                                try:
                                    kimi = self._get_client_ai(addr)
                                    print(f"🤖 获取AI实例成功")
                                    resp_stream = kimi.get_response_stream(text)
                                    print(f"🤖 AI响应流获取成功")
                                    mp3_bytes = self.tts_udp.generate_mp3_from_stream(resp_stream)
                                    print(f"🔊 TTS生成完成，大小: {len(mp3_bytes) if mp3_bytes else 0} 字节")
                                    if mp3_bytes:
                                        print(f"生成 MP3，大小: {len(mp3_bytes)} 字节，发送给 {addr}")
                                        self._send_mp3_safe(addr, mp3_bytes)
                                    else:
                                        print("⚠️ TTS 生成失败，可能是服务暂时不可用，跳过本次回复")
                                except Exception as e:
                                    print(f"❌ AI对话生成失败: {e}")
                                    import traceback
                                    print(f"详细错误: {traceback.format_exc()}")
                    if not processed_any:
                        # 降低 CPU 占用
                        time.sleep(0.005)

                # 定期清理超时客户端（每30秒检查一次）
                if hasattr(self, '_last_cleanup') and time.time() - self._last_cleanup > 30:
                    self.cleanup_inactive_clients()
                    self._last_cleanup = time.time()
                elif not hasattr(self, '_last_cleanup'):
                    self._last_cleanup = time.time()
            except Exception as e:
                print(f"process_loop error: {e}")
                time.sleep(0.01)

if __name__ == "__main__":
    server = UDPVoiceServer(port=UDP_PORT)
    server.start()
    try:
        print("服务器运行中... 按 Ctrl+C 停止")
        print("管理命令:")
        print("  输入 'clients' 查看活跃客户端")
        print("  输入 'reset <ip>:<port>' 重置指定客户端")
        print("  输入 'welcome <ip>' 重置指定IP的欢迎状态")
        print("  输入 'cleanup' 手动清理超时客户端")

        while True:
            try:
                # 非阻塞输入检查（简化版）
                import select
                import sys
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    cmd = input().strip()
                    if cmd == 'clients':
                        print(f"活跃客户端 ({len(server.client_last_activity)}):")
                        for addr, last_time in server.client_last_activity.items():
                            age = time.time() - last_time
                            print(f"  {addr[0]}:{addr[1]} (最后活动: {age:.1f}秒前)")
                    elif cmd.startswith('reset '):
                        try:
                            target = cmd[6:]  # 去掉 'reset '
                            ip, port = target.split(':')
                            addr = (ip, int(port))
                            server.reset_client_session(addr)
                        except:
                            print("格式错误，请使用: reset <ip>:<port>")
                    elif cmd.startswith('welcome '):
                        try:
                            ip = cmd[8:]  # 去掉 'welcome '
                            if ip in server.client_welcomed:
                                server.client_welcomed.remove(ip)
                                if ip in server.client_welcome_time:
                                    del server.client_welcome_time[ip]
                                print(f"✅ 已重置IP {ip} 的欢迎状态，下次连接将重新发送开场白")
                            else:
                                print(f"⚠️ IP {ip} 未在欢迎列表中")
                        except:
                            print("格式错误，请使用: welcome <ip>")
                    elif cmd == 'cleanup':
                        server.cleanup_inactive_clients()
                else:
                    time.sleep(0.1)
            except:
                # Windows 下 select 不支持 stdin，回退到简单模式
                time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("UDPVoiceServer stopped")

