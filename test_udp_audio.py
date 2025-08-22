#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP 音频端到端连通性测试（聚焦新增环节）
- 启动服务器线程，客户端模拟发送分块音频（正弦波）
- 服务器转写+LLM+真实 TTS → MP3 回传
- 用类型检查与回调计数验证最小可用闭环（不做 LLM/TTS 质量评测）
- 附：多客户端同时发送（小规模）
"""

import threading
import time
import socket
import numpy as np

from adpcm_codec import ADPCMCodec, ADPCMProtocol
from simple_udp_server import UDPVoiceServer, UDP_PORT

def gen_sine(sec=1.0, sr=16000, hz=440.0):
    t = np.linspace(0, sec, int(sr*sec), endpoint=False)
    return np.sin(2*np.pi*hz*t).astype(np.float32)

class MiniClient:
    def __init__(self, server=("127.0.0.1", UDP_PORT)):
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.codec = ADPCMCodec()
        self.recv_mp3 = 0

    def send_audio(self, float_audio: np.ndarray, block=512):
        for i in range(0, len(float_audio), block):
            blk = float_audio[i:i+block]
            if len(blk) < block:
                # 填充静音，简化
                blk = np.pad(blk, (0, block-len(blk)))
            pkt = ADPCMProtocol.pack_audio_packet(self.codec.encode(blk), ADPCMProtocol.COMPRESSION_ADPCM)
            self.sock.sendto(pkt, self.server)
            time.sleep(block/16000.0)

    def recv_once(self, timeout=5.0):
        self.sock.settimeout(timeout)
        try:
            pkt, _ = self.sock.recvfrom(65507)
            t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
            if t == ADPCMProtocol.COMPRESSION_TTS_MP3 and len(payload) > 0:
                self.recv_mp3 += 1
                return True
            return False
        except Exception:
            return False


def test_single_client_roundtrip():
    srv = UDPVoiceServer()
    srv_thread = threading.Thread(target=srv.start, daemon=True)
    srv_thread.start()
    time.sleep(1.0)

    cli = MiniClient()
    audio = gen_sine(sec=2.0)
    send_thread = threading.Thread(target=cli.send_audio, args=(audio,), daemon=True)
    send_thread.start()

    ok = cli.recv_once(timeout=15.0)
    assert ok, "未收到服务器返回的 MP3"
    print("✅ 单客户端回传 MP3 成功")
    return True


def test_multi_clients_basic(n=2):
    clients = [MiniClient() for _ in range(n)]
    waves = [gen_sine(sec=1.5, hz=440.0 + i*100) for i in range(n)]

    threads = []
    for c, w in zip(clients, waves):
        th = threading.Thread(target=c.send_audio, args=(w,), daemon=True)
        th.start()
        threads.append(th)

    deadline = time.time() + 20.0
    success = 0
    while time.time() < deadline and success < n:
        for c in clients:
            if c.recv_once(timeout=0.5):
                success += 1
        time.sleep(0.1)

    assert success >= 1, "多客户端至少应有一个收到 MP3 回传"
    print(f"✅ 多客户端基本回传成功：{success}/{n}")
    return True

if __name__ == "__main__":
    ok1 = test_single_client_roundtrip()
    ok2 = test_multi_clients_basic(2)
    print("All tests:", ok1 and ok2)

