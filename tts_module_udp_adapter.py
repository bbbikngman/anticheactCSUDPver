#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge TTS UDP 适配器
- 复用 edge-tts 合成逻辑，返回 MP3 字节（不做本地播放）
- 供 UDP 服务器调用，将 MP3 下发给客户端
"""

import asyncio
import re
import whisper.config as config

class TTSModuleUDPAdapter:
    def __init__(self):
        pass

    async def _edge_tts_bytes_async(self, text: str) -> bytes:
        import edge_tts
        voice = config.TTS_VOICE_ZH if config.LANGUAGE_CODE == "zh" else config.TTS_VOICE_EN
        communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE, volume=config.TTS_VOLUME)
        out = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                out += chunk["data"]
        return out

    def _split_sentences(self, text: str):
        """粗略按句切分，尽量让单句生成的MP3 < 60KB（UDP单包可发）"""
        # 用中英文标点断句，保留标点
        parts = re.split(r"([。！？!?；;]\s*)", text)
        sentences = []
        buf = ""
        for i in range(0, len(parts), 2):
            seg = parts[i] or ""
            punc = parts[i+1] if i+1 < len(parts) else ""
            candidate = (buf + seg + punc).strip()
            # 简单按字符长度控制，避免太长
            if len(candidate) > 50 and buf:
                sentences.append(buf)
                buf = (seg + punc).strip()
            else:
                buf = candidate
        if buf:
            sentences.append(buf)
        # 若切分为空，回退为原文
        return [s for s in sentences if s.strip()] or [text]

    def generate_mp3_from_stream(self, text_stream) -> bytes:
        # 保持原有接口：整段返回
        text = "".join(part for part in text_stream)
        if not text.strip():
            return b""
        return asyncio.run(self._edge_tts_bytes_async(text))

    def generate_mp3_segments_from_stream(self, text_stream):
        """将文本流切句后逐句 TTS，返回多个 mp3 片段（每段尽量 < 60KB）"""
        text = "".join(part for part in text_stream)
        if not text.strip():
            return []
        segs = self._split_sentences(text)
        mp3_list = []
        for s in segs:
            b = asyncio.run(self._edge_tts_bytes_async(s))
            if b:
                mp3_list.append(b)
        return mp3_list

