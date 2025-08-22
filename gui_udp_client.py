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

import numpy as np
import sounddevice as sd
from tkinter import Tk, Button, Text, END, DISABLED, NORMAL, PhotoImage

from adpcm_codec import ADPCMCodec, ADPCMProtocol

def load_config(config_file="client_config.json"):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件 {config_file} 不存在，使用默认配置")
        return {
            "server": {"ip": "127.0.0.1", "port": 31000},
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

        # 日志到文件
        log_dir = os.path.dirname(config["logging"]["file"])
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(filename=config["logging"]["file"],
                            level=getattr(logging, config["logging"]["level"]),
                            format='%(asctime)s %(levelname)s %(message)s')

        # 接收线程
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

        # 播放队列（解决播放阻塞接收的问题）
        self.play_queue = queue.Queue()
        self.player_thread = threading.Thread(target=self._player_loop, daemon=True)

    def log(self, msg: str):
        print(msg)
        logging.info(msg)
        self.log_queue.put(msg)

    def _recv_loop(self):
        self.log("📡 接收线程已启动，开始监听UDP包...")
        backoff = 0.1
        while True:
            try:
                self.sock.settimeout(2.0)
                pkt, addr = self.sock.recvfrom(self.max_udp_size)
                t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                self.log(f"📦 收到UDP包: 类型={t}, 大小={len(payload)}, 来源={addr}")
                if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                    # 统一协议：每个UDP负载即为可独立播放的MP3片段
                    self.log(f"📤 收到MP3片段，大小: {len(payload)} 字节")
                    self.play_queue.put(payload)
                backoff = 0.1
            except socket.timeout:
                # 静音时没有回复是正常的
                pass
            except Exception as e:
                self.log(f"client recv error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)

    def _player_loop(self):
        """独立播放线程：轮询队列，播放完一个再取下一个"""
        self.log("🎵 播放线程已启动，等待队列中的MP3...")
        while True:
            try:
                # 阻塞等待队列中的MP3
                self.log(f"📥 等待队列中的MP3... (当前队列大小: {self.play_queue.qsize()})")
                audio_bytes = self.play_queue.get()
                if audio_bytes is None:  # 退出信号
                    self.log("🛑 收到退出信号，播放线程结束")
                    break

                self.log(f"📥 从队列取出MP3: {len(audio_bytes)} 字节")

                # 播放这个MP3（阻塞直到播放完成）
                self._play_mp3_bytes(audio_bytes)

                # 播放完成，继续轮询下一个
                self.play_queue.task_done()
                self.log("✅ 播放完成，继续等待下一个...")

            except Exception as e:
                self.log(f"❌ 播放线程错误: {e}")
                import traceback
                self.log(f"详细错误: {traceback.format_exc()}")
                time.sleep(0.1)

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

                # 等待播放完成
                play_start = time.time()
                while pygame.mixer.music.get_busy():
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


    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.log(f"🎤 音频状态: {status}")

        block = indata.flatten().astype(np.float32)

        # 检测音频强度（减少日志）
        volume = np.sqrt(np.mean(block**2))

        try:
            compressed = self.codec.encode(block)
            pkt = ADPCMProtocol.pack_audio_packet(compressed, ADPCMProtocol.COMPRESSION_ADPCM)
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
    app.player_thread.start()
    root.mainloop()

if __name__ == "__main__":
    run_gui()

