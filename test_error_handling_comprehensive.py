"""
统一错误处理系统 - 综合测试套件
测试所有增强功能：错误码元数据、结构化日志、监控指标、重试策略、敏感信息脱敏等
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "AAAtest"))

import pytest
import time
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from gateway.api.factory import create_app
from gateway.utils.error_codes_v2 import ErrorCodeV2, ErrorMetadata
from gateway.utils.exceptions import AppException
from gateway.utils.retry_strategy import (
    RetryStrategy, BackoffStrategy, CircuitBreaker,
    CircuitState, RetryBudget, retry
)
from gateway.api.middleware.exception_handler_v2 import (
    ErrorMetrics, SensitiveDataMasker, ErrorAggregator
)


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


# ==================== 错误码元数据测试 ====================

def test_error_code_v2_metadata():
    """测试增强版错误码元数据"""
    error_code = ErrorCodeV2.ERR_QUANT_001
    metadata = error_code.metadata

    assert isinstance(metadata, ErrorMetadata)
    assert metadata.code == 2001
    assert metadata.http_status == 503
    assert metadata.message == "量化系统未就绪"
    assert metadata.retryable is True
    assert metadata.severity == "critical"
    assert metadata.category == "quant"
    assert metadata.user_action == "系统正在初始化，请稍后重试"
    assert metadata.doc_url == "/docs/quant#system-status"
    assert metadata.log_level == "ERROR"
    assert metadata.alert_enabled is True
    assert "service" in metadata.metrics_tags
    assert metadata.retry_strategy is not None


def test_error_code_v2_properties():
    """测试错误码属性访问"""
    error_code = ErrorCodeV2.ERR_AUTH_002

    assert error_code.code == 1002
    assert error_code.http_status == 401
    assert error_code.message == "无效的API密钥"
    assert error_code.retryable is False
    assert error_code.severity == "error"
    assert error_code.category == "auth"
    assert error_code.user_action == "请检查API密钥是否正确"
    assert error_code.code_str == "ERR_AUTH_002"


def test_error_code_v2_lookup():
    """测试错误码查找"""
    # 按code查找
    found = ErrorCodeV2.from_code(2001)
    assert found == ErrorCodeV2.ERR_QUANT_001

    # 按name查找
    found = ErrorCodeV2.from_name("ERR_QUANT_001")
    assert found == ErrorCodeV2.ERR_QUANT_001

    # 查找不存在的
    assert ErrorCodeV2.from_code(9999) is None
    assert ErrorCodeV2.from_name("ERR_INVALID") is None


def test_error_code_v2_category_filter():
    """测试按类别筛选错误码"""
    quant_errors = ErrorCodeV2.get_all_by_category("quant")
    assert len(quant_errors) == 8
    assert all(e.category == "quant" for e in quant_errors)

    auth_errors = ErrorCodeV2.get_all_by_category("auth")
    assert len(auth_errors) == 4
    assert all(e.category == "auth" for e in auth_errors)


def test_error_code_v2_severity_filter():
    """测试按严重性筛选错误码"""
    critical_errors = ErrorCodeV2.get_critical_errors()
    assert len(critical_errors) > 0
    assert all(e.severity == "critical" for e in critical_errors)

    error_level = ErrorCodeV2.get_all_by_severity("error")
    assert len(error_level) > 0
    assert all(e.severity == "error" for e in error_level)


def test_error_code_v2_format_message():
    """测试动态消息格式化"""
    error_code = ErrorCodeV2.ERR_QUANT_003

    # 基础消息
    assert error_code.message == "策略不存在"

    # 动态格式化（如果支持）
    formatted = error_code.format_message(strategy_name="test_strategy")
    assert formatted is not None


# ==================== 敏感信息脱敏测试 ====================

def test_sensitive_data_masker_dict():
    """测试字典数据脱敏"""
    masker = SensitiveDataMasker()

    data = {
        "username": "testuser",
        "password": "secret123456",
        "api_key": "abcdefghijklmnopqrstuvwxyz123456",
        "email": "test@example.com",
        "normal_field": "normal_value"
    }

    masked = masker.mask_dict(data)

    assert masked["username"] == "testuser"  # 不敏感
    assert masked["password"] == "se***56"  # 脱敏
    assert masked["api_key"] == "ab***36"  # 脱敏
    assert masked["normal_field"] == "normal_value"  # 不敏感


def test_sensitive_data_masker_nested():
    """测试嵌套数据脱敏"""
    masker = SensitiveDataMasker()

    data = {
        "user": {
            "name": "test",
            "password": "secret123",
            "profile": {
                "phone": "13800138000"
            }
        }
    }

    masked = masker.mask_dict(data)

    assert masked["user"]["name"] == "test"
    assert masked["user"]["password"] == "se***23"
    assert "phone" in masked["user"]["profile"]


def test_sensitive_data_masker_string():
    """测试字符串脱敏"""
    masker = SensitiveDataMasker()

    text = "联系方式: test@example.com, 手机: 13800138000"
    masked = masker.mask_string(text)

    assert "test***@example.com" in masked
    assert "138****8000" in masked


# ==================== 错误聚合测试 ====================

def test_error_aggregator():
    """测试错误聚合器"""
    aggregator = ErrorAggregator()

    error_key = "test_error_key"

    # 第一次应该记录
    should_log, count = aggregator.should_log(error_key)
    assert should_log is True
    assert count == 1

    # 第2-9次不应该记录
    for i in range(2, 10):
        should_log, count = aggregator.should_log(error_key)
        assert should_log is False
        assert count == i

    # 第10次应该记录
    should_log, count = aggregator.should_log(error_key)
    assert should_log is True
    assert count == 10


# ==================== 错误指标测试 ====================

def test_error_metrics():
    """测试错误指标收集"""
    metrics = ErrorMetrics()

    # 记录错误
    metrics.record_error(
        error_code="ERR_TEST_001",
        category="test",
        severity="error",
        http_status=500,
        duration_ms=123.45,
        tags={"test": "value"}
    )

    # 验证计数
    count = metrics.get_error_count("ERR_TEST_001", "test")
    assert count == 1

    # 再次记录
    metrics.record_error(
        error_code="ERR_TEST_001",
        category="test",
        severity="error",
        http_status=500,
        duration_ms=234.56
    )

    count = metrics.get_error_count("ERR_TEST_001", "test")
    assert count == 2

    # 获取所有指标
    all_metrics = metrics.get_metrics()
    assert "error_counts" in all_metrics
    assert "last_errors" in all_metrics


# ==================== 重试策略测试 ====================

def test_retry_strategy_linear_backoff():
    """测试线性退避"""
    strategy = RetryStrategy(
        max_retries=3,
        base_delay=1.0,
        backoff=BackoffStrategy.LINEAR,
        jitter=False
    )

    assert strategy.calculate_delay(1) == 1.0
    assert strategy.calculate_delay(2) == 2.0
    assert strategy.calculate_delay(3) == 3.0


def test_retry_strategy_exponential_backoff():
    """测试指数退避"""
    strategy = RetryStrategy(
        max_retries=4,
        base_delay=1.0,
        backoff=BackoffStrategy.EXPONENTIAL,
        jitter=False
    )

    assert strategy.calculate_delay(1) == 1.0
    assert strategy.calculate_delay(2) == 2.0
    assert strategy.calculate_delay(3) == 4.0
    assert strategy.calculate_delay(4) == 8.0


def test_retry_strategy_max_delay():
    """测试最大延迟限制"""
    strategy = RetryStrategy(
        max_retries=10,
        base_delay=1.0,
        max_delay=5.0,
        backoff=BackoffStrategy.EXPONENTIAL,
        jitter=False
    )

    # 即使指数增长，也不应超过max_delay
    assert strategy.calculate_delay(10) <= 5.0


def test_retry_strategy_jitter():
    """测试抖动"""
    strategy = RetryStrategy(
        max_retries=3,
        base_delay=1.0,
        backoff=BackoffStrategy.LINEAR,
        jitter=True
    )

    # 抖动应该在0.5-1.5倍之间
    delay = strategy.calculate_delay(1)
    assert 0.5 <= delay <= 1.5


def test_retry_strategy_should_retry():
    """测试重试判断"""
    strategy = RetryStrategy(max_retries=3)

    # 普通异常应该重试
    assert strategy.should_retry(Exception("test"), 1) is True

    # 超过最大次数不应该重试
    assert strategy.should_retry(Exception("test"), 3) is False

    # 不可重试的错误码
    exc = AppException(ErrorCodeV2.ERR_AUTH_001)
    assert strategy.should_retry(exc, 1) is False

    # 可重试的错误码
    exc = AppException(ErrorCodeV2.ERR_QUANT_001)
    assert strategy.should_retry(exc, 1) is True


def test_retry_strategy_execute():
    """测试重试执行"""
    call_count = 0

    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"

    strategy = RetryStrategy(
        max_retries=5,
        base_delay=0.01,  # 快速测试
        jitter=False
    )

    result = strategy.execute(failing_function)

    assert result == "success"
    assert call_count == 3


def test_retry_decorator():
    """测试重试装饰器"""
    call_count = 0

    @retry(max_retries=3, base_delay=0.01, jitter=False)
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Temporary failure")
        return "success"

    result = failing_function()

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_async():
    """测试异步重试"""
    call_count = 0

    @retry(max_retries=3, base_delay=0.01, jitter=False)
    async def failing_async_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Temporary failure")
        return "success"

    result = await failing_async_function()

    assert result == "success"
    assert call_count == 2


# ==================== 断路器测试 ====================

def test_circuit_breaker_closed_state():
    """测试断路器关闭状态"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

    assert breaker.state == CircuitState.CLOSED

    # 成功调用
    result = breaker.call(lambda: "success")
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_open_state():
    """测试断路器打开状态"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

    # 连续失败
    for i in range(3):
        try:
            breaker.call(lambda: 1/0)
        except ZeroDivisionError:
            pass

    assert breaker.state == CircuitState.OPEN

    # 断路器打开后应该拒绝调用
    with pytest.raises(AppException) as exc_info:
        breaker.call(lambda: "test")

    assert "断路器" in str(exc_info.value.message)


def test_circuit_breaker_half_open_state():
    """测试断路器半开状态"""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    # 触发断路器打开
    for i in range(2):
        try:
            breaker.call(lambda: 1/0)
        except ZeroDivisionError:
            pass

    assert breaker.state == CircuitState.OPEN

    # 等待恢复超时
    time.sleep(0.15)

    # 下次调用应该进入半开状态
    result = breaker.call(lambda: "success")
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED


# ==================== 重试预算测试 ====================

def test_retry_budget():
    """测试重试预算"""
    budget = RetryBudget(budget_per_second=5)

    # 初始预算应该可用
    assert budget.can_retry() is True

    # 消耗预算
    for i in range(5):
        budget.consume()

    # 预算耗尽
    assert budget.can_retry() is False

    # 等待补充
    time.sleep(1.1)
    assert budget.can_retry() is True


# ==================== 端到端测试 ====================

def test_e2e_trace_id_propagation(client):
    """测试trace_id端到端传播"""
    custom_trace_id = "test-trace-12345"

    response = client.get("/health", headers={"X-Trace-ID": custom_trace_id})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_trace_id


def test_e2e_error_response_format(client):
    """测试错误响应格式"""
    # 触发一个错误
    response = client.get("/api/v1/quant/platform/overview")

    if response.status_code >= 400:
        data = response.json()

        assert "success" in data
        assert data["success"] is False
        assert "error" in data

        error = data["error"]
        assert "code" in error
        assert "code_str" in error
        assert "message" in error
        assert "user_action" in error
        assert "severity" in error
        assert "retryable" in error
        assert "trace_id" in error


def test_e2e_validation_error(client):
    """测试数据验证错误"""
    # 发送无效数据
    response = client.post("/api/v1/quant/research/run", json={})

    if response.status_code == 422:
        data = response.json()

        assert data["success"] is False
        assert data["error"]["code_str"] == "ERR_SYS_006"
        assert "validation_errors" in data["error"]


# ==================== 性能测试 ====================

def test_performance_error_code_lookup():
    """测试错误码查找性能"""
    import time

    start = time.time()
    for _ in range(10000):
        ErrorCodeV2.from_code(2001)
    elapsed = time.time() - start

    # 10000次查找应该在1秒内完成
    assert elapsed < 1.0


def test_performance_sensitive_masking():
    """测试敏感信息脱敏性能"""
    masker = SensitiveDataMasker()

    data = {
        "password": "secret123456",
        "api_key": "abcdefghijklmnopqrstuvwxyz",
        "nested": {
            "token": "xyz123",
            "data": "normal"
        }
    }

    start = time.time()
    for _ in range(1000):
        masker.mask_dict(data)
    elapsed = time.time() - start

    # 1000次脱敏应该在1秒内完成
    assert elapsed < 1.0


# ==================== 集成测试 ====================

def test_integration_retry_with_circuit_breaker():
    """测试重试与断路器集成"""
    call_count = 0

    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)
    strategy = RetryStrategy(
        max_retries=5,
        base_delay=0.01,
        circuit_breaker=breaker
    )

    def failing_function():
        nonlocal call_count
        call_count += 1
        raise Exception("Always fails")

    # 应该在断路器打开前停止重试
    with pytest.raises(Exception):
        strategy.execute(failing_function)

    assert breaker.state == CircuitState.OPEN
    assert call_count == 3  # 断路器阈值


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
