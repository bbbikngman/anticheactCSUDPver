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

    def log(self, msg: str):
        print(msg)
        logging.info(msg)
        self.log_queue.put(msg)

    def _recv_loop(self):
        backoff = 0.1
        while True:
            try:
                self.sock.settimeout(2.0)
                pkt, _ = self.sock.recvfrom(self.max_udp_size)
                t, payload = ADPCMProtocol.unpack_audio_packet(pkt)
                if t == ADPCMProtocol.COMPRESSION_TTS_MP3:
                    # 兼容两种格式：
                    # A) 直接MP3字节（单包）
                    # B) 自定义分片头: [uint16 总片数][uint16 当前序号] + MP3数据
                    import struct
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
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)

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
    root.mainloop()

if __name__ == "__main__":
    run_gui()

