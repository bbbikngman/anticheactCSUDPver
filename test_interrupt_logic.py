#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整打断逻辑功能
"""

import time
import threading
from simple_udp_server import UDPVoiceServer

def test_filler_word_filtering():
    """测试语气词过滤功能"""
    print("🧪 测试语气词过滤功能...")
    
    # 创建服务器实例（不启动）
    server = UDPVoiceServer()
    
    # 测试用例
    test_cases = [
        # (输入文本, 预期结果, 描述)
        ("嗯", False, "单个语气词"),
        ("啊啊啊", False, "重复语气词"),
        ("嗯 啊 呃", False, "组合语气词"),
        ("那个 这个", False, "组合语气词2"),
        ("你好", True, "正常文本"),
        ("我想问一下", True, "正常问句"),
        ("", False, "空文本"),
        ("a", False, "太短文本"),
        ("咳咳", False, "噪音词"),
        ("um well", False, "英文语气词"),
        ("hello world", True, "英文正常文本"),
    ]
    
    success_count = 0
    for text, expected, description in test_cases:
        result = server._is_valid_interrupt_text(text)
        if result == expected:
            print(f"✅ {description}: '{text}' -> {result}")
            success_count += 1
        else:
            print(f"❌ {description}: '{text}' -> {result}, 预期 {expected}")
    
    print(f"语气词过滤测试: {success_count}/{len(test_cases)} 通过")
    return success_count == len(test_cases)

def test_interrupt_cooldown():
    """测试打断冷却机制"""
    print("\n🧪 测试打断冷却机制...")
    
    server = UDPVoiceServer()
    test_addr = ("127.0.0.1", 12345)
    
    # 测试成功打断的长冷却
    server._set_interrupt_cooldown(test_addr, successful_interrupt=True)
    state = server._get_client_state(test_addr)
    
    now = time.time()
    expected_cooldown = now + server.INTERRUPT_COOLDOWN
    actual_cooldown = state['interrupt_cooldown']
    
    if abs(actual_cooldown - expected_cooldown) < 0.1:
        print("✅ 成功打断冷却时间设置正确")
        success1 = True
    else:
        print(f"❌ 成功打断冷却时间错误: {actual_cooldown} vs {expected_cooldown}")
        success1 = False
    
    # 测试尝试打断的短冷却
    server._set_interrupt_cooldown(test_addr, successful_interrupt=False)
    state = server._get_client_state(test_addr)
    
    expected_cooldown = now + server.ATTEMPT_COOLDOWN
    actual_cooldown = state['interrupt_cooldown']
    
    if abs(actual_cooldown - expected_cooldown) < 0.1:
        print("✅ 尝试打断冷却时间设置正确")
        success2 = True
    else:
        print(f"❌ 尝试打断冷却时间错误: {actual_cooldown} vs {expected_cooldown}")
        success2 = False
    
    return success1 and success2

def test_client_state_management():
    """测试客户端状态管理"""
    print("\n🧪 测试客户端状态管理...")
    
    server = UDPVoiceServer()
    test_addr = ("127.0.0.1", 12345)
    
    # 测试初始状态
    initial_state = server._get_client_state(test_addr)
    expected_initial = {
        'active_session': '',
        'current_chunk': 0,
        'interrupt_cooldown': 0.0,
        'last_interrupt_time': 0.0
    }
    
    if initial_state == expected_initial:
        print("✅ 初始状态正确")
        success1 = True
    else:
        print(f"❌ 初始状态错误: {initial_state}")
        success1 = False
    
    # 测试状态更新
    test_session = "test_session_123"
    test_chunk = 5
    
    server._update_client_chunk(test_addr, test_session, test_chunk)
    updated_state = server._get_client_state(test_addr)
    
    if (updated_state['active_session'] == test_session and 
        updated_state['current_chunk'] == test_chunk):
        print("✅ 状态更新正确")
        success2 = True
    else:
        print(f"❌ 状态更新错误: {updated_state}")
        success2 = False
    
    return success1 and success2

def test_thread_safety():
    """测试线程安全性"""
    print("\n🧪 测试线程安全性...")
    
    server = UDPVoiceServer()
    test_addr = ("127.0.0.1", 12345)
    
    # 并发更新测试
    def update_worker(worker_id):
        for i in range(100):
            session_id = f"session_{worker_id}_{i}"
            chunk_id = i
            server._update_client_chunk(test_addr, session_id, chunk_id)
            time.sleep(0.001)  # 小延迟增加竞争
    
    # 启动多个线程
    threads = []
    for i in range(5):
        thread = threading.Thread(target=update_worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查最终状态
    final_state = server._get_client_state(test_addr)
    
    # 应该有一个有效的session和chunk
    if (final_state['active_session'] and 
        isinstance(final_state['current_chunk'], int) and
        final_state['current_chunk'] >= 0):
        print("✅ 线程安全测试通过")
        return True
    else:
        print(f"❌ 线程安全测试失败: {final_state}")
        return False

def test_interrupt_conditions():
    """测试打断条件检查"""
    print("\n🧪 测试打断条件检查...")
    
    server = UDPVoiceServer()
    test_addr = ("127.0.0.1", 12345)
    
    # 禁用WebSocket检查以便测试其他条件
    server.interrupt_enabled = True
    
    # 测试1: 无活跃session
    result1 = server._atomic_interrupt_check_and_trigger(test_addr, "你好")
    if not result1:
        print("✅ 无活跃session时正确拒绝打断")
        success1 = True
    else:
        print("❌ 无活跃session时应该拒绝打断")
        success1 = False
    
    # 测试2: 设置活跃session后，语气词被过滤
    server._update_client_chunk(test_addr, "test_session", 1)
    result2 = server._atomic_interrupt_check_and_trigger(test_addr, "嗯")
    if not result2:
        print("✅ 语气词正确被过滤")
        success2 = True
    else:
        print("❌ 语气词应该被过滤")
        success2 = False
    
    # 测试3: 冷却期内拒绝打断
    server._set_interrupt_cooldown(test_addr, successful_interrupt=True)
    result3 = server._atomic_interrupt_check_and_trigger(test_addr, "你好")
    if not result3:
        print("✅ 冷却期内正确拒绝打断")
        success3 = True
    else:
        print("❌ 冷却期内应该拒绝打断")
        success3 = False
    
    return success1 and success2 and success3

if __name__ == "__main__":
    print("=" * 50)
    print("完整打断逻辑测试")
    print("=" * 50)
    
    try:
        success1 = test_filler_word_filtering()
        success2 = test_interrupt_cooldown()
        success3 = test_client_state_management()
        success4 = test_thread_safety()
        success5 = test_interrupt_conditions()
        
        total_success = sum([success1, success2, success3, success4, success5])
        
        print(f"\n📊 测试结果: {total_success}/5 通过")
        
        if total_success == 5:
            print("🎉 所有打断逻辑测试通过！")
        else:
            print("❌ 部分测试失败，需要修复")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
