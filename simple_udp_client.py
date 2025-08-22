#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小改动 UDP 客户端
- 录音：float32/16kHz/mono/512块
- 压缩：ADPCM（4:1）
- 发送：UDP 到服务器（端口 31000）
- 接收：MP3 下行，一次性播放
"""

import socket
import threading
import tempfile
import time
import os
import json
import struct
from queue import Queue, Empty

import numpy as np
import sounddevice as sd

from adpcm_codec import ADPCMCodec, ADPCMProtocol

# 读取配置（如果存在）
def load_config(path="client_config.json"):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"server": {"ip": "127.0.0.1", "port": 31000}}

_cfg = load_config()
SERVER_IP = _cfg["server"].get("ip", "127.0.0.1")
SERVER_PORT = int(_cfg["server"].get("port", 31000))
MAX_UDP = 65507

class UDPVoiceClient:
    def __init__(self, server_ip: str = SERVER_IP, server_port: int = SERVER_PORT):
        self.server = (server_ip, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Windows UDP 10054 兼容：关闭 ICMP Port Unreachable 触发的异常
        try:
            SIO_UDP_CONNRESET = 0x9800000C
            self.sock.ioctl(SIO_UDP_CONNRESET, False)
        except Exception:
            pass

        self.codec = ADPCMCodec()
        self.running = True

        # 接收线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

    def start(self):
        self.recv_thread.start()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass

    def _recv_loop(self):
        backoff = 0.1
        while self.running:
            try:
                self.sock.settimeout(2.0)
                pkt, _ = self.sock.recvfrom(MAX_UDP)
                t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                    print(f"收到 MP3 回复，大小: {len(payload)} 字节")
                    # 非阻塞投递到播放线程，避免主接收线程被阻塞
                    if not hasattr(self, '_play_q'):
                        self._play_q = Queue()
                        threading.Thread(target=self._player_loop, daemon=True).start()
                    try:
                        self._play_q.put_nowait(payload)
                    except Exception:
                        pass
                backoff = 0.1  # 成功则重置退避
            except socket.timeout:
                # 静音状态下的超时是正常的，不打印错误
                pass
            except Exception as e:
                print(f"client recv error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)

    def _player_loop(self):
        """独立播放线程，串行播放队列中的MP3，避免阻塞接收线程"""
        while True:
            try:
                payload = self._play_q.get()
                self._play_mp3_bytes(payload)
            except Exception:
                time.sleep(0.01)

    def _play_mp3_bytes(self, audio_bytes: bytes):
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                path = tmp.name
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.quit()
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                pygame.mixer.music.unload()
            finally:
                try:
                    os.unlink(path)
                except:
                    pass
        except Exception as e:
            print(f"play mp3 error: {e}")

    def send_block(self, float_block: np.ndarray):
        compressed = self.codec.encode(float_block)
        pkt = ADPCMProtocol.pack_audio_packet(compressed, ADPCMProtocol.COMPRESSION_ADPCM)
        try:
            self.sock.sendto(pkt, self.server)
            
        except Exception as e:
            print(f"发送失败: {e}")


def main():
    client = UDPVoiceClient()
    client.start()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(status)
        block = indata.flatten().astype(np.float32)
        client.send_block(block)

    try:
        with sd.InputStream(dtype='float32', channels=1, samplerate=16000, blocksize=512, callback=audio_callback):
            print("UDPVoiceClient started. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except Exception as e:
        print(f"audio stream error: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    main()

