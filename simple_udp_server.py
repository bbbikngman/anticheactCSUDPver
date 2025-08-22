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
from tts_module_udp_adapter import TTSModuleUDPAdapter

UDP_PORT = 31000
MAX_UDP = 65507

class UDPVoiceServer:
    def __init__(self, host: str = "0.0.0.0", port: int = UDP_PORT):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        self.running = True

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
        print(f"UDPVoiceServer listening on {self.addr}")
        self.recv_thread.start()
        self.proc_thread.start()

    def stop(self):
        self.running = False
        self.sock.close()

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

    def _send_opening_statement(self, addr: Tuple[str,int]):
        """向新客户端发送开场白"""
        try:
            print(f"为新客户端 {addr} 生成开场白...")
            kimi = self._get_client_ai(addr)
            opening_stream = kimi.generate_opening_statement()
            mp3_bytes = self.tts_udp.generate_mp3_from_stream(opening_stream)
            if mp3_bytes:
                print(f"开场白 MP3 大小: {len(mp3_bytes)} 字节")
                # 直接分片发送以匹配客户端按片播放
                self._send_large_mp3(addr, mp3_bytes)
        except Exception as e:
            print(f"开场白发送失败: {e}")

    def _send_mp3_safe(self, addr: Tuple[str,int], mp3_bytes: bytes):
        """安全发送 MP3（自动处理分片）"""
        # 检查 UDP 包大小限制
        max_payload = 60000  # 留一些余量给协议头
        if len(mp3_bytes) > max_payload:
            print(f"⚠️ MP3 过大 ({len(mp3_bytes)} 字节)，分片发送...")
            self._send_large_mp3(addr, mp3_bytes)
        else:
            try:
                down = ADPCMProtocol.pack_audio_packet(mp3_bytes, ADPCMProtocol.COMPRESSION_TTS_MP3)
                self.sock.sendto(down, addr)
                print(f"✅ MP3 发送成功给 {addr}")
            except Exception as e:
                print(f"MP3 发送失败: {e}")

    def _send_large_mp3(self, addr: Tuple[str,int], mp3_bytes: bytes):
        """分片发送大的 MP3 文件（带序号）"""
        import struct
        chunk_size = 50000  # 50KB 每片
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
                compression_type, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                if compression_type == ADPCMProtocol.COMPRESSION_ADPCM:
                    # 更新客户端活动时间
                    self.client_last_activity[addr] = time.time()

                    # 新客户端首次连接，立即发送开场白
                    if addr not in self.client_welcomed:
                        self.client_welcomed.add(addr)
                        self._send_opening_statement(addr)

                    codec = self._get_client_codec(addr)
                    float_block = codec.decode(payload)  # float32 PCM ~512
                    q = self._get_client_queue(addr)
                    try:
                        q.put_nowait(float_block)
                    except queue.Full:
                        _ = q.get_nowait()
                        q.put_nowait(float_block)
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
                        is_speech = self.vad.is_speech(float_block)
                        handler = self._get_client_handler(addr)
                        triggered = handler.process_chunk(float_block, is_speech)
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
                                print(f"开始 AI 对话生成...")
                                kimi = self._get_client_ai(addr)
                                resp_stream = kimi.get_response_stream(text)
                                mp3_bytes = self.tts_udp.generate_mp3_from_stream(resp_stream)
                                if mp3_bytes:
                                    print(f"生成 MP3，大小: {len(mp3_bytes)} 字节，发送给 {addr}")
                                    self._send_mp3_safe(addr, mp3_bytes)
                                else:
                                    print("TTS 生成失败，无 MP3 数据")
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

