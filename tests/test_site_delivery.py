from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module


def test_root_serves_product_site():
    client = TestClient(main_module.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "ESG Quant IO" in response.text
    assert '/app/#/dashboard' in response.text
    assert 'data-app-entry="dashboard"' in response.text
    assert '/api/v1/quant/platform/overview' in response.text


def test_app_and_blueprint_entrypoints_exist():
    client = TestClient(main_module.app)

    app_response = client.get("/app")
    assert app_response.status_code in {200, 307}

    assert Path("api/main.py").exists()
    assert Path("config/settings.py").exists()
    assert Path("backtest/backtest_engine.py").exists()
