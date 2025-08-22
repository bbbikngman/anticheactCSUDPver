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

    def _tts_bytes_with_size_limit(self, text: str, max_bytes: int = 60000):
        """
        生成不超过 max_bytes 的 MP3 片段；若超限则按文本再细分并递归生成。
        返回: List[bytes]
        """
        if not text.strip():
            return []
        b = asyncio.run(self._edge_tts_bytes_async(text))
        if len(b) <= max_bytes:
            return [b] if b else []
        # 超限，进一步把文本切小再生成
        # 优先在中间附近的标点或空格处分割
        mid = max(1, len(text) // 2)
        seps = ['。','！','？','!','?','，',',','；',';','、',' ']
        split_pos = -1
        # 向左找
        for sep in seps:
            p = text.rfind(sep, 0, mid)
            if p != -1:
                split_pos = max(split_pos, p)
        if split_pos == -1:
            # 向右找
            for sep in seps:
                p = text.find(sep, mid)
                if p != -1:
                    split_pos = p
                    break
        if split_pos == -1:
            split_pos = mid
        left = text[:split_pos+1].strip()
        right = text[split_pos+1:].strip()
        # 防止死循环：如果无法有效分割，进行粗暴均分
        if not left or not right:
            left = text[:mid]
            right = text[mid:]
        res = []
        res.extend(self._tts_bytes_with_size_limit(left, max_bytes))
        res.extend(self._tts_bytes_with_size_limit(right, max_bytes))
        return res

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
            # 确保每个片段都不超过 UDP 安全上限
            seg_bytes_list = self._tts_bytes_with_size_limit(s, max_bytes=58000)
            mp3_list.extend(seg_bytes_list)
        return mp3_list

