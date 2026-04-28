"""
测试异步化端点
验证所有改造后的API端点是否正常工作
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8012/api"

async def test_health_check():
    """测试健康检查端点"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"✓ Health Check: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200

async def test_system_status():
    """测试系统状态端点"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/status")
        print(f"✓ System Status: {response.status_code}")
        data = response.json()
        print(f"  Modules: {data.get('modules', {})}")
        return response.status_code == 200

async def test_session_creation():
    """测试会话创建（异步数据库操作）"""
    async with httpx.AsyncClient() as client:
        session_id = f"test_session_{datetime.now().timestamp()}"
        response = await client.post(
            f"{BASE_URL}/session",
            params={"session_id": session_id, "user_id": "test_user"}
        )
        print(f"✓ Session Creation: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200, session_id

async def test_history_retrieval(session_id):
    """测试历史记录检索（异步数据库操作）"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/history/{session_id}")
        print(f"✓ History Retrieval: {response.status_code}")
        data = response.json()
        print(f"  Messages: {len(data.get('messages', []))}")
        return response.status_code == 200

async def test_auth_status():
    """测试认证状态端点"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/auth/status")
        print(f"✓ Auth Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200

async def test_dashboard_overview():
    """测试仪表板概览端点"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/dashboard/overview")
        print(f"✓ Dashboard Overview: {response.status_code}")
        data = response.json()
        print(f"  Signals: {len(data.get('signals', []))}")
        return response.status_code == 200

async def test_market_data():
    """测试市场数据端点"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/market/ohlcv?symbol=NVDA&timeframe=1D&limit=10")
        print(f"✓ Market Data: {response.status_code}")
        data = response.json()
        print(f"  Candles: {len(data.get('candles', []))}")
        return response.status_code == 200

async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("异步端点测试")
    print("=" * 60)
    print()

    results = []

    # 基础健康检查
    print("1. 基础健康检查")
    print("-" * 60)
    try:
        result = await test_health_check()
        results.append(("Health Check", result))
    except Exception as e:
        print(f"✗ Health Check Failed: {e}")
        results.append(("Health Check", False))
    print()

    # 系统状态
    print("2. 系统状态检查")
    print("-" * 60)
    try:
        result = await test_system_status()
        results.append(("System Status", result))
    except Exception as e:
        print(f"✗ System Status Failed: {e}")
        results.append(("System Status", False))
    print()

    # 会话管理（异步数据库）
    print("3. 会话管理（异步数据库操作）")
    print("-" * 60)
    try:
        result, session_id = await test_session_creation()
        results.append(("Session Creation", result))

        if result:
            # 测试历史记录检索
            history_result = await test_history_retrieval(session_id)
            results.append(("History Retrieval", history_result))
    except Exception as e:
        print(f"✗ Session Management Failed: {e}")
        results.append(("Session Creation", False))
        results.append(("History Retrieval", False))
    print()

    # 认证状态
    print("4. 认证状态")
    print("-" * 60)
    try:
        result = await test_auth_status()
        results.append(("Auth Status", result))
    except Exception as e:
        print(f"✗ Auth Status Failed: {e}")
        results.append(("Auth Status", False))
    print()

    # 仪表板概览
    print("5. 仪表板概览")
    print("-" * 60)
    try:
        result = await test_dashboard_overview()
        results.append(("Dashboard Overview", result))
    except Exception as e:
        print(f"✗ Dashboard Overview Failed: {e}")
        results.append(("Dashboard Overview", False))
    print()

    # 市场数据
    print("6. 市场数据")
    print("-" * 60)
    try:
        result = await test_market_data()
        results.append(("Market Data", result))
    except Exception as e:
        print(f"✗ Market Data Failed: {e}")
        results.append(("Market Data", False))
    print()

    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"通过: {passed}/{total} ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！异步化改造成功！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要进一步检查")

    return passed == total

if __name__ == "__main__":
    print("启动异步端点测试...")
    print("确保后端服务运行在 http://localhost:8012")
    print()

    try:
        success = asyncio.run(run_all_tests())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        exit(1)
    except Exception as e:
        print(f"\n测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
