#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本 - 验证修复后的功能
"""

def test_initialization():
    """测试初始化是否正常"""
    print("🔧 测试模块初始化...")
    
    try:
        from brain_ai_module import BrainAIModule
        from brain_ai_websocket import BrainAIWebSocketModule
        
        print("1. 测试HTTP版本初始化...")
        http_ai = BrainAIModule()
        print(f"   ✅ HTTP AI初始化成功，上下文限制: {http_ai.max_context_messages}条")
        print(f"   ✅ 缓存状态: {'启用' if http_ai.use_cache else '禁用'}")
        
        print("\n2. 测试WebSocket版本初始化...")
        websocket_ai = BrainAIWebSocketModule()
        print(f"   ✅ WebSocket AI初始化成功，上下文限制: {websocket_ai.max_context_messages}条")
        print(f"   ✅ 缓存状态: {'启用' if websocket_ai.use_cache else '禁用'}")
        
        return http_ai, websocket_ai
        
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_simple_response():
    """测试简单回复"""
    print("\n🗣️ 测试简单回复...")
    
    http_ai, websocket_ai = test_initialization()
    if not http_ai or not websocket_ai:
        return
    
    test_input = "您好"
    
    print(f"\n测试输入: {test_input}")
    
    # 测试HTTP版本
    print("\n1. HTTP版本回复:")
    try:
        response = ""
        for chunk in http_ai.get_response_stream(test_input):
            response += chunk
            print(chunk, end="", flush=True)
        print(f"\n   ✅ HTTP回复完成，长度: {len(response)}字符")
    except Exception as e:
        print(f"\n   ❌ HTTP回复失败: {e}")
    
    # 测试WebSocket版本
    print("\n2. WebSocket版本回复:")
    try:
        response = ""
        for chunk in websocket_ai.get_response_stream(test_input):
            response += chunk
            print(chunk, end="", flush=True)
        print(f"\n   ✅ WebSocket回复完成，长度: {len(response)}字符")
    except Exception as e:
        print(f"\n   ❌ WebSocket回复失败: {e}")

def test_context_management():
    """测试上下文管理"""
    print("\n📚 测试上下文管理...")
    
    from brain_ai_module import BrainAIModule
    ai = BrainAIModule()
    
    print(f"初始上下文限制: {ai.max_context_messages}条")
    
    # 模拟多轮对话
    test_inputs = [
        "我叫张三",
        "我今年30岁", 
        "我住在北京",
        "你还记得我的名字吗？"
    ]
    
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n轮次 {i}: {user_input}")
        try:
            response = ""
            for chunk in ai.get_response_stream(user_input):
                response += chunk
            print(f"AI: {response[:100]}...")
            print(f"📊 {ai.get_conversation_summary()}")
        except Exception as e:
            print(f"❌ 轮次 {i} 失败: {e}")

def main():
    """主测试函数"""
    print("🚀 快速功能测试")
    print("=" * 50)
    
    # 测试初始化
    test_initialization()
    
    # 测试简单回复
    test_simple_response()
    
    # 测试上下文管理
    test_context_management()
    
    print("\n" + "=" * 50)
    print("✅ 快速测试完成！")
    print("\n如果所有测试都通过，可以运行完整的性能测试：")
    print("python performance_test.py")

if __name__ == "__main__":
    main()
