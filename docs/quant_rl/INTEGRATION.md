# Integration Steps

在现有 `gateway.main` 创建 FastAPI `app` 之后添加：

```python
from api.include_quant_rl import register_quant_rl
register_quant_rl(app)
```

建议 rollout：

1. demo 数据 smoke test
2. 单资产先跑 DQN / IQL
3. 对接现有 backtest / report
4. 再接 paper execution
5. 最后 guarded live candidate
