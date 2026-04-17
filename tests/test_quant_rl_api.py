from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.include_quant_rl import register_quant_rl


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
