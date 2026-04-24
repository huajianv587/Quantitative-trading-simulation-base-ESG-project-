"""
API安全测试脚本
测试JWT认证和速率限制功能
"""
import asyncio
import time
from typing import Dict, Any
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "full_suite_source_bundle_20260421"))

from gateway.middleware.jwt_auth import JWTAuth
from gateway.middleware.rate_limit import RateLimiter
from gateway.config.security import SecurityConfig


class SecurityTester:
    """安全功能测试器"""

    def __init__(self):
        self.results = {
            "jwt_tests": [],
            "rate_limit_tests": [],
            "password_tests": []
        }

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 70)
        print("API安全功能测试")
        print("=" * 70)
        print()

        # JWT测试
        print("📝 测试1: JWT认证功能")
        print("-" * 70)
        await self.test_jwt_auth()
        print()

        # 速率限制测试
        print("🚦 测试2: 速率限制功能")
        print("-" * 70)
        await self.test_rate_limit()
        print()

        # 密码策略测试
        print("🔒 测试3: 密码策略验证")
        print("-" * 70)
        self.test_password_policy()
        print()

        # 配置测试
        print("⚙️ 测试4: 安全配置")
        print("-" * 70)
        self.test_security_config()
        print()

        # 生成报告
        self.generate_report()

    async def test_jwt_auth(self):
        """测试JWT认证"""
        tests = [
            ("创建JWT令牌", self._test_create_token),
            ("验证有效令牌", self._test_verify_valid_token),
            ("验证过期令牌", self._test_verify_expired_token),
            ("刷新令牌", self._test_refresh_token),
        ]

        for name, test_func in tests:
            try:
                result = await test_func()
                self.results["jwt_tests"].append({
                    "name": name,
                    "status": "✅ PASS" if result else "❌ FAIL",
                    "details": result
                })
                print(f"  {'✅' if result else '❌'} {name}: {result}")
            except Exception as e:
                self.results["jwt_tests"].append({
                    "name": name,
                    "status": "❌ ERROR",
                    "details": str(e)
                })
                print(f"  ❌ {name}: ERROR - {e}")

    async def _test_create_token(self) -> str:
        """测试创建令牌"""
        token = JWTAuth.create_token(
            user_id="test_user_123",
            email="test@example.com",
            role="user"
        )
        return f"Token created (length={len(token)})"

    async def _test_verify_valid_token(self) -> str:
        """测试验证有效令牌"""
        token = JWTAuth.create_token(
            user_id="test_user_123",
            email="test@example.com",
            role="user"
        )

        payload = JWTAuth.verify_token(token)
        return f"Token verified (user_id={payload['user_id']}, email={payload['email']})"

    async def _test_verify_expired_token(self) -> str:
        """测试验证过期令牌"""
        # 创建一个立即过期的令牌
        token = JWTAuth.create_token(
            user_id="test_user_123",
            email="test@example.com",
            role="user",
            expires_in=1  # 1秒后过期
        )

        # 等待令牌过期
        await asyncio.sleep(2)

        try:
            JWTAuth.verify_token(token)
            return "FAIL: Expired token was accepted"
        except Exception as e:
            return f"Expired token correctly rejected: {str(e)[:50]}"

    async def _test_refresh_token(self) -> str:
        """测试刷新令牌"""
        old_token = JWTAuth.create_token(
            user_id="test_user_123",
            email="test@example.com",
            role="user"
        )

        new_token = JWTAuth.refresh_token(old_token)

        old_payload = JWTAuth.verify_token(old_token)
        new_payload = JWTAuth.verify_token(new_token)

        return f"Token refreshed (old_exp={old_payload['exp']}, new_exp={new_payload['exp']})"

    async def test_rate_limit(self):
        """测试速率限制"""
        limiter = RateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5
        )

        tests = [
            ("正常请求", self._test_normal_requests, limiter),
            ("突发请求", self._test_burst_requests, limiter),
            ("超限请求", self._test_exceed_limit, limiter),
        ]

        for name, test_func, *args in tests:
            try:
                result = await test_func(*args)
                self.results["rate_limit_tests"].append({
                    "name": name,
                    "status": "✅ PASS" if result else "❌ FAIL",
                    "details": result
                })
                print(f"  {'✅' if result else '❌'} {name}: {result}")
            except Exception as e:
                self.results["rate_limit_tests"].append({
                    "name": name,
                    "status": "❌ ERROR",
                    "details": str(e)
                })
                print(f"  ❌ {name}: ERROR - {e}")

    async def _test_normal_requests(self, limiter: RateLimiter) -> str:
        """测试正常请求"""
        client_id = "test_client_1"
        success_count = 0

        for i in range(5):
            allowed, quota = await limiter.check_rate_limit(client_id)
            if allowed:
                success_count += 1

        return f"5 requests sent, {success_count} allowed (remaining={quota['remaining_minute']})"

    async def _test_burst_requests(self, limiter: RateLimiter) -> str:
        """测试突发请求"""
        client_id = "test_client_2"
        success_count = 0

        # 快速发送10个请求
        for i in range(10):
            allowed, quota = await limiter.check_rate_limit(client_id)
            if allowed:
                success_count += 1

        return f"10 burst requests sent, {success_count} allowed (limit=10)"

    async def _test_exceed_limit(self, limiter: RateLimiter) -> str:
        """测试超限请求"""
        client_id = "test_client_3"
        success_count = 0
        blocked_count = 0

        # 发送15个请求（超过限制）
        for i in range(15):
            allowed, quota = await limiter.check_rate_limit(client_id)
            if allowed:
                success_count += 1
            else:
                blocked_count += 1

        return f"15 requests sent, {success_count} allowed, {blocked_count} blocked"

    def test_password_policy(self):
        """测试密码策略"""
        test_passwords = [
            ("short", False, "太短"),
            ("validpassword123", True, "有效密码"),
            ("NoDigits", False, "无数字"),
            ("no_uppercase123", False, "无大写"),
            ("NO_LOWERCASE123", False, "无小写"),
        ]

        for password, expected_valid, description in test_passwords:
            is_valid, error = SecurityConfig.validate_password(password)

            result = {
                "name": f"密码: {description}",
                "status": "✅ PASS" if is_valid == expected_valid else "❌ FAIL",
                "details": f"Valid={is_valid}, Error={error if error else 'None'}"
            }

            self.results["password_tests"].append(result)
            print(f"  {result['status']} {result['name']}: {result['details']}")

    def test_security_config(self):
        """测试安全配置"""
        config = SecurityConfig.get_summary()

        print(f"  📋 JWT配置:")
        print(f"     - 过期时间: {config['jwt']['expiration_hours']}小时")
        print(f"     - 刷新令牌过期: {config['jwt']['refresh_expiration_days']}天")

        print(f"  📋 速率限制:")
        print(f"     - 每分钟: {config['rate_limit']['per_minute']}请求")
        print(f"     - 每小时: {config['rate_limit']['per_hour']}请求")
        print(f"     - 突发大小: {config['rate_limit']['burst_size']}")

        print(f"  📋 密码策略:")
        print(f"     - 最小长度: {config['password_policy']['min_length']}")
        print(f"     - 要求大写: {config['password_policy']['require_uppercase']}")
        print(f"     - 要求小写: {config['password_policy']['require_lowercase']}")
        print(f"     - 要求数字: {config['password_policy']['require_digit']}")
        print(f"     - 要求特殊字符: {config['password_policy']['require_special']}")

        print(f"  📋 会话配置:")
        print(f"     - 超时时间: {config['session']['timeout_minutes']}分钟")
        print(f"     - 最大并发: {config['session']['max_concurrent']}")

        print(f"  📋 环境: {config['environment']}")

    def generate_report(self):
        """生成测试报告"""
        print("=" * 70)
        print("测试报告")
        print("=" * 70)
        print()

        # 统计结果
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0

        for category in ["jwt_tests", "rate_limit_tests", "password_tests"]:
            for test in self.results[category]:
                total_tests += 1
                if "PASS" in test["status"]:
                    passed_tests += 1
                elif "FAIL" in test["status"]:
                    failed_tests += 1
                elif "ERROR" in test["status"]:
                    error_tests += 1

        print(f"总测试数: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"❌ 失败: {failed_tests}")
        print(f"⚠️ 错误: {error_tests}")
        print()

        # 通过率
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"通过率: {pass_rate:.1f}%")
        print()

        # 详细结果
        if failed_tests > 0 or error_tests > 0:
            print("失败/错误的测试:")
            print("-" * 70)
            for category in ["jwt_tests", "rate_limit_tests", "password_tests"]:
                for test in self.results[category]:
                    if "FAIL" in test["status"] or "ERROR" in test["status"]:
                        print(f"  {test['status']} {test['name']}")
                        print(f"     详情: {test['details']}")
            print()

        # 总结
        if passed_tests == total_tests:
            print("🎉 所有测试通过！API安全功能正常工作。")
        else:
            print("⚠️ 部分测试失败，请检查上述详情。")


async def main():
    """主函数"""
    tester = SecurityTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
