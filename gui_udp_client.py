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

import numpy as np
import sounddevice as sd
from tkinter import Tk, Button, Text, END, DISABLED, NORMAL, PhotoImage

from adpcm_codec import ADPCMCodec, ADPCMProtocol

SERVER_IP = "127.0.0.1"
SERVER_PORT = 31000
MAX_UDP = 65507

class GUIClient:
    def __init__(self, server_ip: str = SERVER_IP, server_port: int = SERVER_PORT):
        self.server = (server_ip, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.codec = ADPCMCodec()
        self.running = False
        self.stream = None
        self.log_queue = queue.Queue()
        self.mp3_buffer = b""  # 用于拼接分片的 MP3
        self.last_mp3_time = 0  # 最后收到 MP3 片段的时间

        # 日志到文件
        os.makedirs('logs', exist_ok=True)
        logging.basicConfig(filename=os.path.join('logs', 'client.log'),
                            level=logging.INFO,
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
                pkt, _ = self.sock.recvfrom(MAX_UDP)
                t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                    current_time = time.time()

                    # 如果距离上次收到片段超过 2 秒，清空缓冲区（新的 MP3 开始）
                    if current_time - self.last_mp3_time > 2.0:
                        self.mp3_buffer = b""

                    self.last_mp3_time = current_time
                    self.mp3_buffer += payload

                    self.log(f"收到 MP3 片段: {len(payload)} 字节，总计: {len(self.mp3_buffer)} 字节")

                    # 检查是否是完整的 MP3
                    if self._is_complete_mp3(self.mp3_buffer):
                        self.log(f"MP3 接收完成，开始播放: {len(self.mp3_buffer)} 字节")
                        self._play_mp3_bytes(self.mp3_buffer)
                        self.mp3_buffer = b""  # 清空缓冲区
                    else:
                        # 设置超时，如果 1 秒内没有新片段就尝试播放
                        threading.Timer(1.0, self._try_play_buffered_mp3).start()
                backoff = 0.1
            except socket.timeout:
                # 静音时没有回复是正常的
                pass
            except Exception as e:
                self.log(f"client recv error: {e}")
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
            self.log(f"play mp3 error: {e}")

    def _is_complete_mp3(self, data: bytes) -> bool:
        """检查是否是完整的 MP3 文件"""
        if len(data) < 10:
            return False

        # 检查 MP3 头部标识
        has_id3 = data[:3] == b'ID3'
        has_mp3_frame = data[:2] == b'\xff\xfb' or data[:2] == b'\xff\xfa'

        if has_id3 or has_mp3_frame:
            # 如果数据足够大，认为可能是完整的
            if len(data) > 5000:  # 至少 5KB
                return True

        # 检查是否包含 MP3 结束标识或足够大
        return len(data) > 50000  # 如果超过 50KB，强制播放

    def _try_play_buffered_mp3(self):
        """尝试播放缓冲区中的 MP3（超时机制）"""
        if len(self.mp3_buffer) > 1000:  # 至少有一些数据
            current_time = time.time()
            # 如果距离最后一个片段超过 1 秒，尝试播放
            if current_time - self.last_mp3_time >= 1.0:
                self.log(f"超时播放缓冲的 MP3: {len(self.mp3_buffer)} 字节")
                self._play_mp3_bytes(self.mp3_buffer)
                self.mp3_buffer = b""

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.log(str(status))
        block = indata.flatten().astype(np.float32)
        try:
            compressed = self.codec.encode(block)
            pkt = ADPCMProtocol.pack_audio_packet(compressed, ADPCMProtocol.COMPRESSION_ADPCM)
            self.sock.sendto(pkt, self.server)
        except Exception as e:
            self.log(f"发送失败: {e}")

    def start_stream(self):
        if self.running:
            return
        try:
            # 发送连接信号，触发服务器发送开场白
            hello_pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_HELLO)
            self.sock.sendto(hello_pkt, self.server)

            self.stream = sd.InputStream(dtype='float32', channels=1, samplerate=16000, blocksize=512, callback=self._audio_callback)
            self.stream.start()
            self.running = True
            self.log("🎙️ 已开始采集，等待开场白...")
        except Exception as e:
            self.log(f"audio stream error: {e}")

    def reset_session(self):
        try:
            pkt = ADPCMProtocol.pack_control(ADPCMProtocol.CONTROL_RESET)
            self.sock.sendto(pkt, self.server)
            # 客户端本地也清一下编码状态，视觉上更干净
            self.codec.reset_all()
            self.log("🧹 已请求服务器重置会话（提示词级）")
        except Exception as e:
            self.log(f"reset error: {e}")

    def close(self):
        try:
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
    
    root = Tk(); root.title("反诈AI 客户端")
    root.geometry("420x280")

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

