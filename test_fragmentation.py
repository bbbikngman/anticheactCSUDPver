#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试分包功能
"""

import struct
from adpcm_codec import ADPCMProtocol

def test_large_audio_fragmentation():
    """测试大音频文件的分包功能"""
    print("🧪 测试大音频文件分包...")
    
    # 创建一个大的测试音频数据（100KB）
    large_audio_data = b"FAKE_MP3_DATA_" * 7000  # 约98KB
    test_session_id = "test1234"
    test_chunk_id = 1
    
    print(f"原始音频大小: {len(large_audio_data)} 字节")
    
    # 模拟服务器端的分包逻辑
    MAX_UDP_PAYLOAD = 60000
    HEADER_SIZE = 21
    MAX_AUDIO_PER_PACKET = MAX_UDP_PAYLOAD - HEADER_SIZE  # 59979字节
    
    if len(large_audio_data) <= MAX_AUDIO_PER_PACKET:
        print("❌ 音频数据太小，不会触发分包")
        return False
    
    # 计算分包数
    total_fragments = (len(large_audio_data) + MAX_AUDIO_PER_PACKET - 1) // MAX_AUDIO_PER_PACKET
    print(f"需要分包数: {total_fragments}")
    
    # 模拟分包发送和接收
    fragments = []
    for fragment_index in range(total_fragments):
        start_pos = fragment_index * MAX_AUDIO_PER_PACKET
        end_pos = min(start_pos + MAX_AUDIO_PER_PACKET, len(large_audio_data))
        fragment_data = large_audio_data[start_pos:end_pos]
        
        print(f"分包 {fragment_index+1}/{total_fragments}: {len(fragment_data)} 字节")
        
        # 打包
        packet = ADPCMProtocol.pack_audio_with_session(
            fragment_data, test_session_id, test_chunk_id,
            ADPCMProtocol.COMPRESSION_TTS_MP3,
            fragment_index=fragment_index, total_fragments=total_fragments
        )
        
        # 解包验证
        compression_type, session_id, chunk_id, frag_idx, total_frags, audio_data = ADPCMProtocol.unpack_audio_with_session(packet)
        
        # 验证
        assert compression_type == ADPCMProtocol.COMPRESSION_TTS_MP3
        assert session_id == test_session_id
        assert chunk_id == test_chunk_id
        assert frag_idx == fragment_index
        assert total_frags == total_fragments
        assert audio_data == fragment_data
        
        fragments.append(audio_data)
        print(f"✅ 分包 {fragment_index+1} 验证通过")
    
    # 重组验证
    reconstructed_data = b"".join(fragments)
    if reconstructed_data == large_audio_data:
        print("✅ 分包重组验证通过！")
        return True
    else:
        print("❌ 分包重组失败！")
        return False

def test_small_audio_no_fragmentation():
    """测试小音频文件不分包"""
    print("\n🧪 测试小音频文件不分包...")
    
    small_audio_data = b"SMALL_MP3_DATA"
    test_session_id = "small123"
    test_chunk_id = 5
    
    print(f"小音频大小: {len(small_audio_data)} 字节")
    
    # 打包（应该不分包）
    packet = ADPCMProtocol.pack_audio_with_session(
        small_audio_data, test_session_id, test_chunk_id,
        ADPCMProtocol.COMPRESSION_TTS_MP3,
        fragment_index=0, total_fragments=1
    )
    
    # 解包验证
    compression_type, session_id, chunk_id, frag_idx, total_frags, audio_data = ADPCMProtocol.unpack_audio_with_session(packet)
    
    # 验证
    assert compression_type == ADPCMProtocol.COMPRESSION_TTS_MP3
    assert session_id == test_session_id
    assert chunk_id == test_chunk_id
    assert frag_idx == 0
    assert total_frags == 1
    assert audio_data == small_audio_data
    
    print("✅ 小音频不分包验证通过！")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("分包功能测试")
    print("=" * 50)
    
    success1 = test_large_audio_fragmentation()
    success2 = test_small_audio_no_fragmentation()
    
    if success1 and success2:
        print("\n🎉 所有分包测试通过！")
    else:
        print("\n❌ 分包测试失败！")
