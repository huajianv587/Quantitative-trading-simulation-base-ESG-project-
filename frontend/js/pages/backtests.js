import * as base from './backtest.js';

export async function render(container) {
  await base.render(container);
  const button = container.querySelector('#btn-run-bt');
  if (button && !container.querySelector('#run-backtest-btn')) {
    button.id = 'run-backtest-btn';
  }
}

export function destroy() {
  if (base.destroy) return base.destroy();
}
