# -*- coding: utf-8 -*-
"""
离线测试：使用“檔頭快取 + 即時拼接”策略对捕获的chunks进行解码验证。
将 config.CAPTURE_WEBM_CHUNKS=true 并运行web服务，录入几秒语音后，会在 CAPTURE_DIR 下生成若干 .webm 文件。
然后运行本脚本，对这些文件按序进行解码，输出成功率与每块样本数。
"""
from __future__ import annotations
import glob
import os
from pathlib import Path
from typing import List

from whisper.utils.webm_stream_decoder import WebMStreamDecoder


def run_test(capture_dir: str):
    files: List[str] = sorted(glob.glob(os.path.join(capture_dir, "*.webm")))
    if not files:
        print("未找到捕获的chunks，请先设置 CAPTURE_WEBM_CHUNKS=true 并运行服务录入语音")
        return

    dec = WebMStreamDecoder(target_sr=16000, target_channels=1)
    total = 0
    ok = 0
    total_samples = 0

    for f in files:
        with open(f, 'rb') as fh:
            data = fh.read()
        pcm_bytes, n = dec.decode_chunk(data)
        total += 1
        if n > 0:
            ok += 1
            total_samples += n
            print(f"✓ {os.path.basename(f)} -> {n} samples")
        else:
            print(f"✗ {os.path.basename(f)} -> decode failed")

    rate = (ok / total * 100.0) if total else 0.0
    dur_sec = total_samples / 16000.0
    print(f"解码成功: {ok}/{total} ({rate:.2f}%), 总样本: {total_samples} (~{dur_sec:.2f}s)")


if __name__ == "__main__":
    cap_dir = os.environ.get("CAPTURE_DIR", "./captured_chunks")
    run_test(cap_dir)

