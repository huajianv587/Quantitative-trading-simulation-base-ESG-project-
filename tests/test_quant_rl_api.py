from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes_quant_rl import service as rl_service
from api.include_quant_rl import register_quant_rl
from quant_rl.infrastructure.types import RunInfo


def test_quant_rl_routes_smoke():
    app = FastAPI()
    register_quant_rl(app)
    client = TestClient(app)
    resp = client.get('/api/v1/quant/rl/overview')
    assert resp.status_code == 200
    assert 'stack' in resp.json()

    recipe = client.post('/api/v1/quant/rl/recipes/build', json={'recipe_key': 'L1_price_tech', 'limit': 80})
    assert recipe.status_code == 200
    recipe_payload = recipe.json()
    assert recipe_payload['recipe']['key'] == 'L1_price_tech'

    search = client.post(
        '/api/v1/quant/rl/search',
        json={'recipe_key': 'L1_price_tech', 'dataset_path': recipe_payload['merged_dataset_path'], 'trials': 1, 'quick_steps': 20},
    )
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload['best_trial'] == 0
    assert search_payload['best_params']

    demo = rl_service.generate_demo_dataset()
    report_path = rl_service.artifact_store.save_text('test-promote-run', 'report.txt', 'ok')
    rl_service.repo.save(
        RunInfo(
            run_id='test-promote-run',
            algorithm='hybrid_frontier',
            phase='evaluation_backtest',
            status='backtested',
            config={
                'dataset_path': demo['dataset_path'],
                'dataset_id': 'rl-demo-market',
                'protection_status': 'pass',
                'required_data_tier': 'l1',
            },
            metrics={'sharpe': 1.0},
            artifacts={'report_path': report_path},
        )
    )
    promote = client.post(
        '/api/v1/quant/rl/promote',
        json={'run_id': 'test-promote-run', 'strategy_id': 'rl_timing_overlay', 'required_data_tier': 'l2'},
    )
    assert promote.status_code == 200
    promote_payload = promote.json()
    assert promote_payload['run_id'] == 'test-promote-run'
    assert promote_payload['promotion_status'] in {'promoted', 'research_only'}
