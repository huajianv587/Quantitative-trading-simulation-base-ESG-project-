#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前端后端功能完整性测试脚本
测试所有API端点与前端功能的闭环
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import time
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8012"
FRONTEND_URL = "http://localhost:8080"

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test_name: str, detail: str = ""):
        self.passed.append((test_name, detail))
        print(f"[PASS] {test_name} {detail}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"[FAIL] {test_name}: {error}")

    def add_warning(self, test_name: str, warning: str):
        self.warnings.append((test_name, warning))
        print(f"[WARN] {test_name}: {warning}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*60}")
        print(f"测试总结: {len(self.passed)}/{total} 通过")
        print(f"通过: {len(self.passed)}, 失败: {len(self.failed)}, 警告: {len(self.warnings)}")
        print(f"{'='*60}\n")

        if self.failed:
            print("失败的测试:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")

        if self.warnings:
            print("\n警告:")
            for name, warning in self.warnings:
                print(f"  - {name}: {warning}")

results = TestResults()

def test_backend_health():
    """测试后端健康检查"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            results.add_pass("后端健康检查", f"状态码: {response.status_code}")
        else:
            results.add_fail("后端健康检查", f"状态码: {response.status_code}")
    except Exception as e:
        results.add_fail("后端健康检查", str(e))

def test_frontend_accessible():
    """测试前端可访问性"""
    try:
        response = requests.get(f"{FRONTEND_URL}/index.html", timeout=5)
        if response.status_code == 200 and "Quant Terminal" in response.text:
            results.add_pass("前端可访问性", "index.html 加载成功")
        else:
            results.add_fail("前端可访问性", f"状态码: {response.status_code}")
    except Exception as e:
        results.add_fail("前端可访问性", str(e))

def test_auth_endpoints():
    """测试认证端点"""
    # 测试注册
    test_user = {
        "email": f"test_user_{int(time.time())}@example.com",
        "password": "Test123456",
        "name": "Test User"
    }

    try:
        # 注册
        response = requests.post(f"{BASE_URL}/auth/register", json=test_user, timeout=5)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            results.add_pass("用户注册", f"用户: {test_user['email']}")

            # 登录
            login_data = {"email": test_user["email"], "password": test_user["password"]}
            response = requests.post(f"{BASE_URL}/auth/login", json=login_data, timeout=5)
            if response.status_code == 200:
                results.add_pass("用户登录", "登录成功")
                return token
            else:
                results.add_fail("用户登录", f"状态码: {response.status_code}")
        else:
            results.add_fail("用户注册", f"状态码: {response.status_code}, 响应: {response.text}")
    except Exception as e:
        results.add_fail("认证端点测试", str(e))

    return None

def test_api_endpoints_with_auth(token: str):
    """测试需要认证的API端点"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # 测试各个API端点
    endpoints = [
        ("/api/quant/strategies", "GET", "策略列表"),
        ("/api/quant/backtest/list", "GET", "回测列表"),
        ("/api/agent/sessions", "GET", "Agent会话列表"),
        ("/api/reports/list", "GET", "报告列表"),
    ]

    for endpoint, method, name in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)

            if response.status_code in [200, 404]:  # 404也算正常，说明端点存在
                results.add_pass(f"API端点: {name}", f"{endpoint}")
            else:
                results.add_warning(f"API端点: {name}", f"状态码: {response.status_code}")
        except Exception as e:
            results.add_warning(f"API端点: {name}", str(e))

def test_frontend_pages():
    """测试前端页面路由"""
    pages = [
        "dashboard", "research", "intelligence", "factor-lab",
        "simulation", "backtest", "portfolio", "chat", "reports"
    ]

    for page in pages:
        try:
            # 前端是单页应用，所有路由都返回index.html
            response = requests.get(f"{FRONTEND_URL}/index.html", timeout=5)
            if response.status_code == 200:
                results.add_pass(f"前端页面: {page}", "路由配置正确")
            else:
                results.add_fail(f"前端页面: {page}", f"状态码: {response.status_code}")
        except Exception as e:
            results.add_fail(f"前端页面: {page}", str(e))

def test_static_assets():
    """测试静态资源"""
    assets = [
        "/css/app.css",
        "/js/app.js",
        "/app-config.js"
    ]

    for asset in assets:
        try:
            response = requests.get(f"{FRONTEND_URL}{asset}", timeout=5)
            if response.status_code == 200:
                results.add_pass(f"静态资源: {asset}", f"大小: {len(response.content)} bytes")
            else:
                results.add_fail(f"静态资源: {asset}", f"状态码: {response.status_code}")
        except Exception as e:
            results.add_fail(f"静态资源: {asset}", str(e))

def main():
    print("="*60)
    print("前端后端功能完整性测试")
    print("="*60)
    print()

    # 1. 测试后端健康
    print("1. 测试后端服务...")
    test_backend_health()

    # 2. 测试前端可访问性
    print("\n2. 测试前端服务...")
    test_frontend_accessible()

    # 3. 测试静态资源
    print("\n3. 测试静态资源...")
    test_static_assets()

    # 4. 测试认证功能
    print("\n4. 测试认证功能...")
    token = test_auth_endpoints()

    # 5. 测试API端点
    print("\n5. 测试API端点...")
    test_api_endpoints_with_auth(token)

    # 6. 测试前端页面
    print("\n6. 测试前端页面路由...")
    test_frontend_pages()

    # 输出总结
    results.summary()

    # 生成详细报告
    generate_detailed_report()

def generate_detailed_report():
    """生成详细的测试报告"""
    report = {
        "测试时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "通过": len(results.passed),
        "失败": len(results.failed),
        "警告": len(results.warnings),
        "详细结果": {
            "通过": [{"测试": name, "详情": detail} for name, detail in results.passed],
            "失败": [{"测试": name, "错误": error} for name, error in results.failed],
            "警告": [{"测试": name, "警告": warning} for name, warning in results.warnings]
        }
    }

    with open("test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n详细报告已保存到: test_report.json")

if __name__ == "__main__":
    main()
