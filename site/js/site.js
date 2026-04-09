async function hydrateLiveStats() {
  const target = document.getElementById('live-stats');
  if (!target) return;

  try {
    const response = await fetch('/api/v1/quant/platform/overview');
    if (!response.ok) return;
    const data = await response.json();
    const storage = data.storage || {};
    const backtest = data.latest_backtest?.metrics || {};

    target.innerHTML = `
      <article class="stat-card">
        <span>股票池</span>
        <strong>${data.universe?.size || 0}</strong>
        <small>${data.universe?.benchmark || 'SPY'} 基准上的默认覆盖</small>
      </article>
      <article class="stat-card">
        <span>工件存储</span>
        <strong>${storage.r2_ready ? 'R2 Active' : 'Local Ready'}</strong>
        <small>${storage.supabase_ready ? 'Supabase metadata online' : 'Supabase waiting for credentials'}</small>
      </article>
      <article class="stat-card">
        <span>最新夏普</span>
        <strong>${backtest.sharpe ?? 0}</strong>
        <small>回撤 ${(Number(backtest.max_drawdown || 0) * 100).toFixed(2)}%</small>
      </article>
    `;
  } catch (error) {
    console.warn('site overview fetch skipped', error);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', hydrateLiveStats);
} else {
  hydrateLiveStats();
}
