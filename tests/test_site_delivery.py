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
    assert '进入控制台' in response.text
    assert '/api/v1/quant/platform/overview' in response.text


def test_app_and_blueprint_entrypoints_exist():
    client = TestClient(main_module.app)

    app_response = client.get("/app")
    assert app_response.status_code in {200, 307}

    app_index_response = client.get("/app/index.html")
    assert app_index_response.status_code == 200
    assert "Quant Terminal" in app_index_response.text
    assert "/app/app-config.js" in app_index_response.text
    assert "ESG Quant IO" not in app_index_response.text

    assert Path("api/main.py").exists()
    assert Path("config/settings.py").exists()
    assert Path("backtest/backtest_engine.py").exists()


def test_launcher_defaults_to_port_1002():
    launcher = Path("start.cmd").read_text(encoding="utf-8")
    api_launcher = Path("_api_server.cmd").read_text(encoding="utf-8")
    ui_launcher = Path("_ui_server.cmd").read_text(encoding="utf-8")

    assert 'set "DEFAULT_PORT=1002"' in launcher
    assert 'set "PORT_CANDIDATES=%DEFAULT_PORT%"' in launcher
    assert 'set "PORT_RANGE_START=%DEFAULT_PORT%"' in launcher
    assert 'set "PORT_RANGE_END=%DEFAULT_PORT%"' in launcher
    assert 'set "API_PORT=1002"' in api_launcher
    assert '--port %API_PORT%' in api_launcher
    assert 'set "UI_PORT=1002"' in ui_launcher
    assert 'set "UI_URL=http://127.0.0.1:%UI_PORT%/app/"' in ui_launcher
