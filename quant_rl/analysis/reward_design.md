# Reward Design Notes

金融 RL 不建议直接用单步 PnL。  
建议结构：

```text
reward
= pnl_component
- transaction_cost
- turnover_penalty * turnover
- drawdown_penalty * current_drawdown
- position_penalty * abs(position)
```

核心目标：

- 减少过度交易
- 限制回撤
- 保持仓位平滑
- 避免 reward hacking
