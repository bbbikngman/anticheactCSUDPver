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

import numpy as np
import sounddevice as sd

from adpcm_codec import ADPCMCodec, ADPCMProtocol

SERVER_IP = "192.168.31.216"
SERVER_PORT = 31000
MAX_UDP = 65507

class UDPVoiceClient:
    def __init__(self, server_ip: str = SERVER_IP, server_port: int = SERVER_PORT):
        self.server = (server_ip, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
                    # 写临时 mp3 并播放（与服务器端逻辑一致）
                    self._play_mp3_bytes(payload)
                backoff = 0.1  # 成功则重置退避
            except socket.timeout:
                # 静音状态下的超时是正常的，不打印错误
                pass
            except Exception as e:
                print(f"client recv error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)

    def _play_mp3_bytes(self, audio_bytes: bytes):
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                path = tmp.name
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
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

