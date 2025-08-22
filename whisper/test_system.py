#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统测试脚本 - 检查所有组件是否正常工作
"""

import sys
import os

def test_imports():
    """测试所有必要的导入"""
    print("🔍 测试导入...")
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"✅ CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✅ CUDA版本: {torch.version.cuda}")
    except ImportError as e:
        print(f"❌ PyTorch导入失败: {e}")
        return False
    
    try:
        import sounddevice as sd
        print("✅ sounddevice")
    except ImportError:
        print("❌ sounddevice导入失败")
        return False
    
    try:
        import faster_whisper
        print("✅ faster-whisper")
    except ImportError:
        print("❌ faster-whisper导入失败")
        return False
    
    try:
        import edge_tts
        print("✅ edge-tts")
    except ImportError:
        print("⚠️ edge-tts导入失败，将使用pyttsx3")
    
    try:
        import pyttsx3
        print("✅ pyttsx3")
    except ImportError:
        print("❌ pyttsx3导入失败")
        return False
    
    return True

def test_config():
    """测试配置文件"""
    print("\n🔍 测试配置...")
    
    if not os.path.exists('.env'):
        print("❌ 未找到.env配置文件")
        return False
    
    try:
        import config
        print("✅ 配置文件加载成功")
        
        if not config.MOONSHOT_API_KEY:
            print("⚠️ 警告：MOONSHOT_API_KEY未设置")
        else:
            print("✅ API密钥已设置")
        
        print(f"✅ TTS引擎: {config.TTS_ENGINE}")
        print(f"✅ 语速设置: {config.TTS_RATE}")
        print(f"✅ 设备设置: {config.DEVICE}")
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False
    
    return True

def test_modules():
    """测试各个模块"""
    print("\n🔍 测试模块...")
    
    try:
        from vad_module import VADModule
        vad = VADModule()
        print("✅ VAD模块")
    except Exception as e:
        print(f"❌ VAD模块失败: {e}")
        return False
    
    try:
        from transcriber_module import TranscriberModule
        import config
        transcriber = TranscriberModule(config.WHISPER_MODEL_SIZE, config.DEVICE)
        print("✅ 语音识别模块")
    except Exception as e:
        print(f"❌ 语音识别模块失败: {e}")
        return False
    
    try:
        from brain_ai_module import BrainAIModule
        brain = BrainAIModule()
        print("✅ AI对话模块")
    except Exception as e:
        print(f"❌ AI对话模块失败: {e}")
        return False
    
    try:
        from tts_module import TTSModule
        import config
        tts = TTSModule(config.DEVICE)
        print("✅ TTS语音合成模块")
    except Exception as e:
        print(f"❌ TTS模块失败: {e}")
        return False
    
    return True

def test_audio_devices():
    """测试音频设备"""
    print("\n🔍 测试音频设备...")
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        
        print(f"✅ 找到 {len(input_devices)} 个输入设备")
        print(f"✅ 找到 {len(output_devices)} 个输出设备")
        
        if len(input_devices) == 0:
            print("❌ 未找到可用的麦克风设备")
            return False
        
        if len(output_devices) == 0:
            print("❌ 未找到可用的音频输出设备")
            return False
        
        # 显示默认设备
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]
        print(f"✅ 默认输入设备: {devices[default_input]['name']}")
        print(f"✅ 默认输出设备: {devices[default_output]['name']}")
        
    except Exception as e:
        print(f"❌ 音频设备测试失败: {e}")
        return False
    
    return True

def main():
    """主测试函数"""
    print("🛡️ 反诈AI电话专员 - 系统测试")
    print("=" * 50)
    
    all_passed = True
    
    # 测试导入
    if not test_imports():
        all_passed = False
    
    # 测试配置
    if not test_config():
        all_passed = False
    
    # 测试模块
    if not test_modules():
        all_passed = False
    
    # 测试音频设备
    if not test_audio_devices():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有测试通过！系统准备就绪。")
        print("💡 现在可以运行: python main.py")
    else:
        print("❌ 部分测试失败，请检查上述错误信息。")
        print("💡 建议运行: setup.bat 重新安装依赖")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
