import * as base from './portfolio.js';

export async function render(container) {
  await base.render(container);

  const optimizeButton = container.querySelector('#btn-optimize');
  if (optimizeButton && !container.querySelector('#optimize-portfolio-btn')) {
    optimizeButton.id = 'optimize-portfolio-btn';
  }

  if (!container.querySelector('#generate-execution-btn') && optimizeButton?.parentElement) {
    const executionButton = document.createElement('button');
    executionButton.id = 'generate-execution-btn';
    executionButton.className = 'btn btn-ghost btn-lg';
    executionButton.style.flex = '1';
    executionButton.textContent = 'Generate Execution';
    executionButton.addEventListener('click', () => {
      const universe = container.querySelector('#p-universe')?.value?.trim() || '';
      const capital = container.querySelector('#p-capital')?.value || '1000000';
      const broker = 'alpaca';
      window.sessionStorage.setItem('qt.execution.prefill', JSON.stringify({ universe, capital, broker }));
      window.location.hash = '#/execution';
    });
    optimizeButton.parentElement.appendChild(executionButton);
  }
}

export function destroy() {
  if (base.destroy) return base.destroy();
}
