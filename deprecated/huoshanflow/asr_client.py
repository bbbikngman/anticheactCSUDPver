# asr_client.py
import asyncio
import json
import struct
import uuid
import logging
import subprocess
import numpy as np # 增加numpy用于生成静音
from typing import Dict, Any, AsyncGenerator

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def convert_audio_to_pcm(audio_path: str) -> bytes:
    logger.info(f"Converting {audio_path} to PCM format...")
    try:
        command = ['ffmpeg', '-v', 'quiet', '-i', audio_path, '-acodec', 'pcm_s16le', '-f', 's16le', '-ac', '1', '-ar', '16000', '-']
        return subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    except Exception as e:
        logger.error(f"FFmpeg conversion failed: {e}")
        raise

class ASRClient:
    def __init__(self, app_id: str, access_token: str):
        self.app_id = app_id
        self.access_token = access_token
        self.url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
        self.resource_id = "volc.bigasr.sauc.duration"
        self.sample_rate = 16000
        self.chunk_duration_ms = 200
        self._session = None
        self._ws = None
        self._is_connected = False
        self._connection_lock = asyncio.Lock()

    async def connect(self):
        async with self._connection_lock:
            if self._is_connected and not self._ws.closed:
                return

            logger.info("Attempting to establish WebSocket connection...")
            
            if self._session and not self._session.closed:
                await self._session.close()

            self._session = aiohttp.ClientSession()
            headers = {
                "X-Api-App-Key": self.app_id,
                "X-Api-Access-Key": self.access_token,
                "X-Api-Resource-Id": self.resource_id,
                "X-Api-Connect-Id": str(uuid.uuid4()),
            }
            try:
                self._ws = await self._session.ws_connect(self.url, headers=headers, heartbeat=20)
                self._is_connected = True
                logger.info("WebSocket connection established successfully.")
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                if self._session:
                    await self._session.close()
                self._is_connected = False
                raise

    async def disconnect(self):
        async with self._connection_lock:
            if not self._is_connected: return
            if self._ws and not self._ws.closed: await self._ws.close()
            if self._session and not self._session.closed: await self._session.close()
            self._is_connected = False
            logger.info("WebSocket connection closed.")

    async def _ensure_connection(self):
        if not self._is_connected or self._ws.closed:
            logger.warning("Connection lost or not established. Reconnecting...")
            await self.connect()

    async def warm_up(self):
        """
        【升级】发送一个更长的静音请求来确保预热效果。
        """
        warm_up_duration_seconds = 3
        logger.info(f"Warming up connection with a {warm_up_duration_seconds}-second silent audio request...")
        logger.info("This may take up to 30 seconds as it triggers the server's cold start...")
        
        # 生成3秒的16-bit静音PCM数据
        silent_audio = np.zeros(int(self.sample_rate * warm_up_duration_seconds), dtype=np.int16).tobytes()
        try:
            # 消耗掉生成器的所有结果，确保请求完整走完
            async for _ in self.transcribe(silent_audio):
                pass
            logger.info("✅ Connection warm-up complete. Service is now hot and ready for real tasks.")
        except Exception as e:
            logger.error(f"An error occurred during warm-up: {e}")

    async def transcribe(self, audio_source: bytes) -> AsyncGenerator[Dict[str, Any], None]:
        await self._ensure_connection()
        
        request_payload = {
            "user": {"uid": "prod_user_01"},
            "audio": {"format": "pcm", "rate": self.sample_rate, "bits": 16, "channel": 1},
            "request": {"model_name": "bigmodel", "enable_punc": True, "show_utterances": True}
        }
        await self._send_json(request_payload, 'full_client_request')
        
        send_queue, receive_queue = asyncio.Queue(), asyncio.Queue()
        sender_task = asyncio.create_task(self._audio_sender(send_queue))
        receiver_task = asyncio.create_task(self._result_receiver(receive_queue))

        chunk_size = int(self.sample_rate * 2 * self.chunk_duration_ms / 1000)
        for i in range(0, len(audio_source), chunk_size):
            await send_queue.put(audio_source[i: i + chunk_size])
        await send_queue.put(None)

        while True:
            result = await receive_queue.get()
            if result is None: break
            yield result
        
        await sender_task
        await receiver_task

    async def _send_json(self, payload: Dict, msg_type: str):
        payload_bytes = json.dumps(payload).encode('utf-8')
        header = self._pack_binary_header(msg_type)
        payload_size = struct.pack('>I', len(payload_bytes))
        await self._ws.send_bytes(header + payload_size + payload_bytes)

    async def _send_audio_chunk(self, chunk: bytes, is_last: bool = False):
        header = self._pack_binary_header('audio_only_request', is_last_package=is_last)
        payload_size = struct.pack('>I', len(chunk))
        await self._ws.send_bytes(header + payload_size + chunk)

    async def _audio_sender(self, queue: asyncio.Queue):
        while True:
            chunk = await queue.get()
            if chunk is None:
                await self._send_audio_chunk(b'', is_last=True)
                break
            await self._send_audio_chunk(chunk)
            await asyncio.sleep(self.chunk_duration_ms / 1000)

    async def _result_receiver(self, queue: asyncio.Queue):
        while True:
            try:
                msg = await self._ws.receive(timeout=40) # 预热可能耗时较长，增加超时
                if msg.type == aiohttp.WSMsgType.BINARY:
                    resp = self._parse_server_message(msg.data)
                    await queue.put(resp)
                    if resp.get("result", {}).get("utterances") and resp["result"]["utterances"][-1].get("definite"):
                        if len(resp["result"].get("text", "")) >= 0:
                            break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
            except asyncio.TimeoutError:
                logger.warning("Receiver timeout.")
                break
        await queue.put(None)
    
    def _pack_binary_header(self, msg_type: str, is_last_package: bool = False) -> bytes:
        protocol_version, header_size, serialization_method, compression_method = 0b0001, 0b0001, 0b0001, 0b0000
        type_map = {'full_client_request': 0b0001, 'audio_only_request': 0b0010}
        message_type = type_map.get(msg_type, 0)
        flags = 0b0010 if is_last_package else 0b0000
        byte1 = (protocol_version << 4) | header_size
        byte2 = (message_type << 4) | flags
        byte3 = (serialization_method << 4) | compression_method
        return struct.pack('>BBBB', byte1, byte2, byte3, 0x00)

    def _parse_server_message(self, data: bytes) -> Dict[str, Any]:
        if len(data) < 4: return {"error": "Message too short"}
        byte2 = data[1]
        message_flags = byte2 & 0x0F
        payload_ptr = 4
        if (message_flags & 0b0001) != 0:
            if len(data) < payload_ptr + 4: return {"error": "Message too short for sequence"}
            payload_ptr += 4
        if len(data) < payload_ptr + 4: return {"error": "Message too short for payload size"}
        payload_size = struct.unpack('>I', data[payload_ptr:payload_ptr+4])[0]
        payload_ptr += 4
        if len(data) < payload_ptr + payload_size: return {"error": "Incomplete payload"}
        payload_data = data[payload_ptr : payload_ptr + payload_size]
        if not payload_data: return {}
        try:
            return json.loads(payload_data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return {"error": f"Payload decode error: {e}"}
