import * as base from './research.js';

export async function render(container) {
  await base.render(container);
  const button = container.querySelector('#btn-run-research');
  if (button && !container.querySelector('#run-research-btn')) {
    button.id = 'run-research-btn';
  }
}

export function destroy() {
  if (base.destroy) return base.destroy();
}
