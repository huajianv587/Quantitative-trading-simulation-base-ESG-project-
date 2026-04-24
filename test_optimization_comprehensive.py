"""
全面优化测试套件

测试覆盖：
1. 缓存系统（三层缓存）
2. 数据库连接池
3. 速率限制
4. 安全加固
5. 性能基准测试
"""
import pytest
import asyncio
import time
from typing import Dict, Any

# 缓存测试
class TestCacheSystem:
    """缓存系统测试"""

    @pytest.mark.asyncio
    async def test_local_cache_basic(self):
        """测试本地缓存基本功能"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache

        cache = LocalCache(max_size=100, ttl=60)

        # 设置和获取
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"

        # 不存在的键
        value = await cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_local_cache_ttl(self):
        """测试本地缓存TTL"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache

        cache = LocalCache(max_size=100, ttl=1)  # 1秒过期

        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"

        # 等待过期
        await asyncio.sleep(1.1)
        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_local_cache_lru_eviction(self):
        """测试LRU淘汰策略"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache

        cache = LocalCache(max_size=3, ttl=60)

        # 填满缓存
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # 添加第4个，应该淘汰key1
        await cache.set("key4", "value4")

        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """测试缓存统计"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache

        cache = LocalCache(max_size=100, ttl=60)

        await cache.set("key1", "value1")
        await cache.get("key1")  # 命中
        await cache.get("key2")  # 未命中

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


# 数据库连接池测试
class TestDatabasePool:
    """数据库连接池测试"""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """测试连接池初始化"""
        from AAAtest.gateway.utils.db_pool import DatabasePool

        # 使用测试DSN
        pool = DatabasePool(
            dsn="postgresql://test:test@localhost:5432/test",
            min_size=2,
            max_size=5
        )

        # 注意：实际测试需要真实数据库
        # 这里只测试对象创建
        assert pool.min_size == 2
        assert pool.max_size == 5

    @pytest.mark.asyncio
    async def test_pool_stats(self):
        """测试连接池统计"""
        from AAAtest.gateway.utils.db_pool import DatabasePool

        pool = DatabasePool(
            dsn="postgresql://test:test@localhost:5432/test",
            min_size=2,
            max_size=5
        )

        stats = pool.get_stats()
        assert "status" in stats
        assert "total_connections" in stats
        assert "config" in stats


# 速率限制测试
class TestRateLimit:
    """速率限制测试"""

    @pytest.mark.asyncio
    async def test_token_bucket_basic(self):
        """测试令牌桶基本功能"""
        from AAAtest.gateway.api.middleware.rate_limit import TokenBucket

        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # 消费令牌
        assert await bucket.consume(5) is True
        assert await bucket.consume(5) is True
        assert await bucket.consume(1) is False  # 超过容量

    @pytest.mark.asyncio
    async def test_token_bucket_refill(self):
        """测试令牌桶补充"""
        from AAAtest.gateway.api.middleware.rate_limit import TokenBucket

        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 每秒补充10个

        # 消费所有令牌
        assert await bucket.consume(10) is True
        assert await bucket.consume(1) is False

        # 等待补充
        await asyncio.sleep(0.5)  # 应该补充5个令牌
        assert await bucket.consume(5) is True

    @pytest.mark.asyncio
    async def test_sliding_window_counter(self):
        """测试滑动窗口计数器"""
        from AAAtest.gateway.api.middleware.rate_limit import SlidingWindowCounter

        counter = SlidingWindowCounter(limit=5, window=1)

        # 允许5个请求
        for _ in range(5):
            assert await counter.is_allowed() is True

        # 第6个请求应该被拒绝
        assert await counter.is_allowed() is False

        # 等待窗口过期
        await asyncio.sleep(1.1)
        assert await counter.is_allowed() is True

    @pytest.mark.asyncio
    async def test_fixed_window_counter(self):
        """测试固定窗口计数器"""
        from AAAtest.gateway.api.middleware.rate_limit import FixedWindowCounter

        counter = FixedWindowCounter(limit=5, window=1)

        # 允许5个请求
        for _ in range(5):
            assert await counter.is_allowed() is True

        # 第6个请求应该被拒绝
        assert await counter.is_allowed() is False

        # 等待窗口重置
        await asyncio.sleep(1.1)
        assert await counter.is_allowed() is True

    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """测试速率限制器"""
        from AAAtest.gateway.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitConfig,
            RateLimitAlgorithm
        )

        config = RateLimitConfig(
            requests=10,
            window=1,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = RateLimiter(config)

        # 测试不同的键
        allowed, _ = await limiter.is_allowed("user1")
        assert allowed is True

        allowed, _ = await limiter.is_allowed("user2")
        assert allowed is True


# 安全测试
class TestSecurity:
    """安全功能测试"""

    def test_sql_injection_detection(self):
        """测试SQL注入检测"""
        from AAAtest.gateway.utils.security import InputValidator

        # 安全输入
        assert InputValidator.validate_sql_injection("normal text") is True
        assert InputValidator.validate_sql_injection("user@example.com") is True

        # 危险输入
        assert InputValidator.validate_sql_injection("DROP TABLE users") is False
        assert InputValidator.validate_sql_injection("'; DELETE FROM users--") is False
        assert InputValidator.validate_sql_injection("UNION SELECT * FROM passwords") is False

    def test_xss_detection(self):
        """测试XSS检测"""
        from AAAtest.gateway.utils.security import InputValidator

        # 安全输入
        assert InputValidator.validate_xss("normal text") is True
        assert InputValidator.validate_xss("Hello World") is True

        # 危险输入
        assert InputValidator.validate_xss("<script>alert('xss')</script>") is False
        assert InputValidator.validate_xss("javascript:alert(1)") is False
        assert InputValidator.validate_xss("<img src=x onerror=alert(1)>") is False

    def test_html_sanitization(self):
        """测试HTML清理"""
        from AAAtest.gateway.utils.security import InputValidator

        input_text = "<script>alert('xss')</script>"
        sanitized = InputValidator.sanitize_html(input_text)
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

    def test_email_validation(self):
        """测试邮箱验证"""
        from AAAtest.gateway.utils.security import InputValidator

        assert InputValidator.validate_email("user@example.com") is True
        assert InputValidator.validate_email("test.user@domain.co.uk") is True
        assert InputValidator.validate_email("invalid-email") is False
        assert InputValidator.validate_email("@example.com") is False

    def test_phone_validation(self):
        """测试手机号验证"""
        from AAAtest.gateway.utils.security import InputValidator

        assert InputValidator.validate_phone("13800138000") is True
        assert InputValidator.validate_phone("15912345678") is True
        assert InputValidator.validate_phone("12345678901") is False
        assert InputValidator.validate_phone("1234567890") is False

    def test_sensitive_data_masking(self):
        """测试敏感数据脱敏"""
        from AAAtest.gateway.utils.security import SensitiveDataMasker

        # 邮箱脱敏
        assert SensitiveDataMasker.mask_email("user@example.com") == "u***r@example.com"

        # 手机号脱敏
        assert SensitiveDataMasker.mask_phone("13800138000") == "138****8000"

        # 身份证脱敏
        assert SensitiveDataMasker.mask_id_card("110101199001011234") == "1101**********1234"

        # 银行卡脱敏
        assert SensitiveDataMasker.mask_bank_card("6222021234567890") == "6222********7890"

        # 密码脱敏
        assert SensitiveDataMasker.mask_password("MyPassword123") == "******"

    def test_dict_masking(self):
        """测试字典脱敏"""
        from AAAtest.gateway.utils.security import SensitiveDataMasker

        data = {
            "username": "testuser",
            "password": "secret123",
            "email": "user@example.com",
            "phone": "13800138000",
            "age": 25
        }

        masked = SensitiveDataMasker.mask_dict(data)
        assert masked["username"] == "testuser"
        assert masked["password"] == "******"
        assert masked["email"] == "u***r@example.com"
        assert masked["phone"] == "138****8000"
        assert masked["age"] == 25

    def test_csrf_token_generation(self):
        """测试CSRF令牌生成"""
        from AAAtest.gateway.utils.security import CSRFProtection

        csrf = CSRFProtection(secret_key="test-secret")

        token1 = csrf.generate_token()
        token2 = csrf.generate_token()

        assert token1 != token2
        assert len(token1) > 20

    def test_csrf_token_validation(self):
        """测试CSRF令牌验证"""
        from AAAtest.gateway.utils.security import CSRFProtection

        csrf = CSRFProtection(secret_key="test-secret", token_expiry=1)

        token = csrf.generate_token()
        assert csrf.validate_token(token) is True
        assert csrf.validate_token("invalid-token") is False

        # 测试过期
        time.sleep(1.1)
        assert csrf.validate_token(token) is False


# 性能测试
class TestPerformance:
    """性能基准测试"""

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """测试缓存性能"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache

        cache = LocalCache(max_size=10000, ttl=60)

        # 写入性能
        start = time.time()
        for i in range(1000):
            await cache.set(f"key{i}", f"value{i}")
        write_time = time.time() - start

        # 读取性能
        start = time.time()
        for i in range(1000):
            await cache.get(f"key{i}")
        read_time = time.time() - start

        print(f"\n缓存性能:")
        print(f"  写入1000次: {write_time:.3f}秒 ({1000/write_time:.0f} ops/s)")
        print(f"  读取1000次: {read_time:.3f}秒 ({1000/read_time:.0f} ops/s)")

        assert write_time < 1.0  # 写入应该在1秒内完成
        assert read_time < 0.5   # 读取应该在0.5秒内完成

    @pytest.mark.asyncio
    async def test_rate_limiter_performance(self):
        """测试速率限制器性能"""
        from AAAtest.gateway.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitConfig,
            RateLimitAlgorithm
        )

        config = RateLimitConfig(
            requests=10000,
            window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = RateLimiter(config)

        # 测试性能
        start = time.time()
        for i in range(1000):
            await limiter.is_allowed(f"user{i % 10}")
        elapsed = time.time() - start

        print(f"\n速率限制器性能:")
        print(f"  1000次检查: {elapsed:.3f}秒 ({1000/elapsed:.0f} ops/s)")

        assert elapsed < 1.0  # 应该在1秒内完成

    def test_security_validation_performance(self):
        """测试安全验证性能"""
        from AAAtest.gateway.utils.security import InputValidator

        test_strings = [
            "normal text",
            "user@example.com",
            "SELECT * FROM users",
            "<script>alert('xss')</script>"
        ] * 250  # 1000个测试

        # SQL注入检测性能
        start = time.time()
        for s in test_strings:
            InputValidator.validate_sql_injection(s)
        sql_time = time.time() - start

        # XSS检测性能
        start = time.time()
        for s in test_strings:
            InputValidator.validate_xss(s)
        xss_time = time.time() - start

        print(f"\n安全验证性能:")
        print(f"  SQL注入检测1000次: {sql_time:.3f}秒 ({1000/sql_time:.0f} ops/s)")
        print(f"  XSS检测1000次: {xss_time:.3f}秒 ({1000/xss_time:.0f} ops/s)")

        assert sql_time < 1.0
        assert xss_time < 1.0


# 集成测试
class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_cache_with_rate_limit(self):
        """测试缓存与速率限制集成"""
        from AAAtest.gateway.utils.cache_v2 import LocalCache
        from AAAtest.gateway.api.middleware.rate_limit import (
            RateLimiter,
            RateLimitConfig,
            RateLimitAlgorithm
        )

        cache = LocalCache(max_size=100, ttl=60)
        config = RateLimitConfig(requests=10, window=1, algorithm=RateLimitAlgorithm.TOKEN_BUCKET)
        limiter = RateLimiter(config)

        # 模拟带速率限制的缓存访问
        user_id = "user123"
        cache_key = f"data:{user_id}"

        # 第一次访问（缓存未命中）
        allowed, _ = await limiter.is_allowed(user_id)
        assert allowed is True

        data = await cache.get(cache_key)
        if data is None:
            data = {"result": "computed"}
            await cache.set(cache_key, data)

        # 第二次访问（缓存命中）
        allowed, _ = await limiter.is_allowed(user_id)
        assert allowed is True

        data = await cache.get(cache_key)
        assert data == {"result": "computed"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
