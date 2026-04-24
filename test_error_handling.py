"""
测试统一错误处理系统
"""
import sys
from pathlib import Path

# 添加AAAtest到路径
sys.path.insert(0, str(Path(__file__).parent / "AAAtest"))

import pytest
from fastapi.testclient import TestClient
from gateway.api.factory import create_app
from gateway.utils.exceptions import QuantException, SystemException
from gateway.utils.error_codes import ErrorCode


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


def test_trace_id_middleware(client):
    """测试trace_id中间件"""
    response = client.get("/health")

    # 验证响应头包含trace_id
    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    assert len(trace_id) == 36  # UUID格式
    assert trace_id.count("-") == 4


def test_custom_trace_id(client):
    """测试自定义trace_id"""
    custom_trace_id = "test-trace-id-12345"
    response = client.get("/health", headers={"X-Trace-ID": custom_trace_id})

    # 验证返回相同的trace_id
    assert response.headers["X-Trace-ID"] == custom_trace_id


def test_quant_system_not_ready_error(client):
    """测试量化系统未就绪错误"""
    # 访问需要量化系统的端点
    response = client.get("/api/v1/quant/platform/overview")

    if response.status_code == 503:
        # 验证错误响应格式
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "error" in data

        error = data["error"]
        assert error["code"] == "ERR_QUANT_001"
        assert "trace_id" in error
        assert error["retryable"] is True
        assert "timestamp" in error


def test_validation_error(client):
    """测试数据验证错误"""
    # 发送无效的请求体
    response = client.post("/api/v1/quant/research/run", json={})

    if response.status_code == 422:
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "error" in data

        error = data["error"]
        assert error["code"] == "ERR_SYS_006"
        assert "validation_errors" in error.get("details", {})


def test_error_code_enum():
    """测试错误码枚举"""
    # 验证错误码属性
    assert ErrorCode.ERR_QUANT_001.code == 2001
    assert ErrorCode.ERR_QUANT_001.http_status == 503
    assert ErrorCode.ERR_QUANT_001.message == "量化系统未就绪"
    assert ErrorCode.ERR_QUANT_001.retryable is True

    # 验证错误码查找
    found = ErrorCode.from_code(2001)
    assert found == ErrorCode.ERR_QUANT_001

    found = ErrorCode.from_name("ERR_QUANT_001")
    assert found == ErrorCode.ERR_QUANT_001


def test_custom_exception():
    """测试自定义异常类"""
    exc = QuantException(
        ErrorCode.ERR_QUANT_002,
        message="自定义消息",
        details={"key": "value"},
        trace_id="test-trace-123"
    )

    assert exc.error_code == ErrorCode.ERR_QUANT_002
    assert exc.message == "自定义消息"
    assert exc.details == {"key": "value"}
    assert exc.trace_id == "test-trace-123"
    assert exc.http_status == 500
    assert exc.code_str == "ERR_QUANT_002"
    assert exc.retryable is True

    # 测试to_dict
    exc_dict = exc.to_dict()
    assert exc_dict["code"] == "ERR_QUANT_002"
    assert exc_dict["message"] == "自定义消息"
    assert exc_dict["details"] == {"key": "value"}
    assert exc_dict["trace_id"] == "test-trace-123"
    assert exc_dict["retryable"] is True


def test_health_endpoint(client):
    """测试健康检查端点"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "modules" in data

    # 验证trace_id在响应头中
    assert "X-Trace-ID" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
