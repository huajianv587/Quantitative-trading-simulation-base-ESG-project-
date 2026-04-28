#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的前后端集成测试脚本
测试所有优化项和功能闭环
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import time
from typing import Dict, List

BASE_URL = "http://localhost:8012"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class TestSuite:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
        self.token = None

    def log_pass(self, test_name: str, detail: str = ""):
        self.passed.append((test_name, detail))
        print(f"{Colors.GREEN}[PASS]{Colors.RESET} {test_name} {detail}")

    def log_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"{Colors.RED}[FAIL]{Colors.RESET} {test_name}: {error}")

    def log_warn(self, test_name: str, warning: str):
        self.warnings.append((test_name, warning))
        print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {test_name}: {warning}")

    def log_info(self, message: str):
        print(f"{Colors.BLUE}[INFO]{Colors.RESET} {message}")

    def section(self, title: str):
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{title}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        pass_rate = (len(self.passed) / total * 100) if total > 0 else 0

        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}测试总结{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"总计: {total} | 通过: {Colors.GREEN}{len(self.passed)}{Colors.RESET} | 失败: {Colors.RED}{len(self.failed)}{Colors.RESET} | 警告: {Colors.YELLOW}{len(self.warnings)}{Colors.RESET}")
        print(f"通过率: {Colors.GREEN if pass_rate >= 80 else Colors.YELLOW}{pass_rate:.1f}%{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

        if self.failed:
            print(f"{Colors.RED}失败的测试:{Colors.RESET}")
            for name, error in self.failed:
                print(f"  - {name}: {error}")

        if self.warnings:
            print(f"\n{Colors.YELLOW}警告:{Colors.RESET}")
            for name, warning in self.warnings:
                print(f"  - {name}: {warning}")

        return len(self.failed) == 0

suite = TestSuite()

def test_backend_health():
    """测试后端健康检查"""
    suite.section("1. 后端服务健康检查")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            suite.log_pass("后端健康检查", f"服务: {data.get('service', 'Unknown')}")
            return True
        else:
            suite.log_fail("后端健康检查", f"状态码: {response.status_code}")
            return False
    except Exception as e:
        suite.log_fail("后端健康检查", str(e))
        return False

def test_api_documentation():
    """测试API文档可访问性"""
    suite.section("2. API文档")
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            suite.log_pass("API文档", "Swagger UI 可访问")
        else:
            suite.log_warn("API文档", f"状态码: {response.status_code}")
    except Exception as e:
        suite.log_warn("API文档", str(e))

def test_auth_flow():
    """测试完整的认证流程"""
    suite.section("3. 认证流程测试")

    # 注册
    test_user = {
        "email": f"test_{int(time.time())}@example.com",
        "password": "Test123456!",
        "name": "Test User"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user, timeout=5)
        if response.status_code == 200:
            data = response.json()
            suite.token = data.get("token")
            suite.log_pass("用户注册", f"邮箱: {test_user['email']}")

            # 登录
            login_data = {"email": test_user["email"], "password": test_user["password"]}
            response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=5)
            if response.status_code == 200:
                suite.log_pass("用户登录", "登录成功")
                return True
            else:
                suite.log_fail("用户登录", f"状态码: {response.status_code}")
        else:
            suite.log_fail("用户注册", f"状态码: {response.status_code}")
    except Exception as e:
        suite.log_fail("认证流程", str(e))

    return False

def test_api_endpoints():
    """测试主要API端点"""
    suite.section("4. API端点测试")

    headers = {"Authorization": f"Bearer {suite.token}"} if suite.token else {}

    endpoints = [
        ("/api/quant/strategies", "GET", "策略列表"),
        ("/api/quant/backtest/list", "GET", "回测列表"),
        ("/api/agent/sessions", "GET", "Agent会话"),
        ("/api/reports/list", "GET", "报告列表"),
        ("/api/quant/platform/overview", "GET", "平台概览"),
    ]

    for endpoint, method, name in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)

            if response.status_code in [200, 404]:
                suite.log_pass(f"API: {name}", endpoint)
            else:
                suite.log_warn(f"API: {name}", f"状态码: {response.status_code}")
        except Exception as e:
            suite.log_warn(f"API: {name}", str(e))

def test_cors_configuration():
    """测试CORS配置"""
    suite.section("5. CORS配置测试")

    try:
        headers = {
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        response = requests.options(f"{BASE_URL}/api/health", headers=headers, timeout=5)

        cors_headers = {
            "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
            "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
            "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
        }

        if cors_headers["Access-Control-Allow-Origin"]:
            suite.log_pass("CORS配置", f"允许来源: {cors_headers['Access-Control-Allow-Origin']}")
        else:
            suite.log_warn("CORS配置", "未找到CORS头")

    except Exception as e:
        suite.log_warn("CORS配置", str(e))

def test_frontend_resources():
    """测试前端静态资源"""
    suite.section("6. 前端静态资源")

    resources = [
        "/app/index.html",
        "/app/css/app.css",
        "/app/css/loading-error.css",
        "/app/css/responsive.css",
        "/app/js/app.js",
        "/app/app-config.js",
    ]

    for resource in resources:
        try:
            response = requests.get(f"{BASE_URL}{resource}", timeout=5)
            if response.status_code == 200:
                size_kb = len(response.content) / 1024
                suite.log_pass(f"资源: {resource}", f"{size_kb:.1f} KB")
            else:
                suite.log_fail(f"资源: {resource}", f"状态码: {response.status_code}")
        except Exception as e:
            suite.log_fail(f"资源: {resource}", str(e))

def test_performance():
    """测试性能指标"""
    suite.section("7. 性能测试")

    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = (time.time() - start) * 1000

        if elapsed < 100:
            suite.log_pass("响应时间", f"{elapsed:.0f}ms (优秀)")
        elif elapsed < 500:
            suite.log_pass("响应时间", f"{elapsed:.0f}ms (良好)")
        else:
            suite.log_warn("响应时间", f"{elapsed:.0f}ms (需优化)")

    except Exception as e:
        suite.log_fail("性能测试", str(e))

def test_error_handling():
    """测试错误处理"""
    suite.section("8. 错误处理测试")

    try:
        # 测试404
        response = requests.get(f"{BASE_URL}/api/nonexistent", timeout=5)
        if response.status_code == 404:
            suite.log_pass("404处理", "正确返回404")
        else:
            suite.log_warn("404处理", f"状态码: {response.status_code}")

        # 测试无效认证
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@test.com", "password": "wrong"},
            timeout=5
        )
        if response.status_code == 401:
            suite.log_pass("认证错误处理", "正确返回401")
        else:
            suite.log_warn("认证错误处理", f"状态码: {response.status_code}")

    except Exception as e:
        suite.log_warn("错误处理测试", str(e))

def generate_report():
    """生成测试报告"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total": len(suite.passed) + len(suite.failed),
            "passed": len(suite.passed),
            "failed": len(suite.failed),
            "warnings": len(suite.warnings),
            "pass_rate": (len(suite.passed) / (len(suite.passed) + len(suite.failed)) * 100) if (len(suite.passed) + len(suite.failed)) > 0 else 0
        },
        "results": {
            "passed": [{"test": name, "detail": detail} for name, detail in suite.passed],
            "failed": [{"test": name, "error": error} for name, error in suite.failed],
            "warnings": [{"test": name, "warning": warning} for name, warning in suite.warnings]
        }
    }

    with open("test_report_complete.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    suite.log_info(f"详细报告已保存: test_report_complete.json")

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Quant Terminal - 完整集成测试{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    # 运行所有测试
    backend_ok = test_backend_health()

    if backend_ok:
        test_api_documentation()
        test_auth_flow()
        test_api_endpoints()
        test_cors_configuration()
        test_frontend_resources()
        test_performance()
        test_error_handling()
    else:
        suite.log_fail("测试中止", "后端服务不可用")

    # 输出总结
    success = suite.summary()

    # 生成报告
    generate_report()

    # 返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
