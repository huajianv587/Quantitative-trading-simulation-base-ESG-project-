/**
 * SVG 仪表盘组件
 * 显示 0-100 分数的圆形仪表盘，无需第三方依赖
 */

import { scoreColor, scoreLabel, scoreClassName } from '../utils.js';

/**
 * 创建仪表盘 SVG
 * @param {number} value - 分数 0-100
 * @param {string} label - 标签文本
 * @param {string} subtitle - 副标签
 * @returns {string} - SVG HTML 字符串
 */
export function createGaugeSVG(value, label = '', subtitle = '') {
  const normalizedValue = Math.max(0, Math.min(100, value));
  const percentage = normalizedValue / 100;
  const angle = percentage * 270; // 270 度圆弧

  // 计算弧线路径
  const radius = 50;
  const circumference = (270 / 360) * 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - percentage);

  const color = scoreColor(normalizedValue);
  const className = scoreClassName(normalizedValue);

  return `
    <svg viewBox="0 0 120 120" class="gauge-svg">
      <!-- 背景弧 -->
      <path
        d="M 10,60 A 50,50 0 1,1 110,60"
        class="gauge-arc-bg"
      />

      <!-- 填充弧 -->
      <path
        d="M 10,60 A 50,50 0 1,1 110,60"
        class="gauge-arc-fill ${className}"
        style="
          stroke-dasharray: ${circumference};
          stroke-dashoffset: ${strokeDashoffset};
          stroke: ${color};
        "
      />

      <!-- 中心文字 -->
      <text x="60" y="55" text-anchor="middle" font-size="24" font-weight="bold" fill="#F0F4F8">
        ${normalizedValue.toFixed(0)}
      </text>
      <text x="60" y="72" text-anchor="middle" font-size="10" fill="#94A3B8">
        ${label || '分数'}
      </text>
      ${subtitle ? `<text x="60" y="84" text-anchor="middle" font-size="8" fill="#64748B">${subtitle}</text>` : ''}
    </svg>
  `;
}

/**
 * 在 DOM 元素中渲染仪表盘
 * @param {HTMLElement} container
 * @param {number} value
 * @param {string} label
 * @param {string} subtitle
 */
export function renderGauge(container, value, label = '', subtitle = '') {
  if (!container) return;

  const svg = createGaugeSVG(value, label, subtitle);

  container.innerHTML = `
    <div class="gauge-container">
      ${svg}
    </div>
  `;
}

/**
 * 创建多个仪表盘 (用于 E/S/G 三维展示)
 * @param {Object} scores - { e_score, s_score, g_score, overall_score }
 * @returns {string} - HTML 字符串
 */
export function createGaugeRow(scores) {
  const { e_score = 0, s_score = 0, g_score = 0, overall_score = 0 } = scores;

  const dims = [
    { label: '综合', value: overall_score, color: '#6366F1' },
    { label: '环境', value: e_score, color: '#10B981' },
    { label: '社会', value: s_score, color: '#3B82F6' },
    { label: '治理', value: g_score, color: '#F59E0B' },
  ];

  return `
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
      ${dims.map(dim => `
        <div class="card text-center">
          <div class="gauge-container" style="height: 120px;">
            ${createGaugeSVG(dim.value, dim.label)}
          </div>
          <div class="text-xs text-[#64748B] mt-2">${scoreLabel(dim.value)}</div>
        </div>
      `).join('')}
    </div>
  `;
}

/**
 * 创建圆形分数徽章 (用于图表中心)
 * @param {number} value
 * @param {number} size - 直径像素数
 * @returns {string} - SVG HTML
 */
export function createCircleBadge(value, size = 80) {
  const color = scoreColor(value);
  const radius = size / 2 - 4;

  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="inline-block">
      <circle cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke="#2D3748" stroke-width="2" />
      <circle cx="${size / 2}" cy="${size / 2}" r="${radius}"
              fill="none" stroke="${color}" stroke-width="2"
              stroke-dasharray="${Math.PI * 2 * radius}"
              stroke-dashoffset="${Math.PI * 2 * radius * (1 - value / 100)}"
              stroke-linecap="round" />
      <text x="${size / 2}" y="${size / 2 + 6}" text-anchor="middle"
            font-size="${size / 4}" font-weight="bold" fill="${color}">
        ${Math.round(value)}
      </text>
    </svg>
  `;
}
