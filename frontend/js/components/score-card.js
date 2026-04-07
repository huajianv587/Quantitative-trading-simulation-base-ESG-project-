/**
 * ESG 评分卡片组件
 * 用于在聊天、报告等地方显示 E/S/G 分数
 */

import { formatScore, scoreColor, scoreLabel } from '../utils.js';

/**
 * 创建评分卡片 HTML
 * @param {Object} scores - { e_score, s_score, g_score, overall_score }
 * @param {Object} confidence - (可选) { confidence: 0-1 }
 * @returns {string} - HTML 字符串
 */
export function createScoreCard(scores, confidence = null) {
  const {
    e_score = 0,
    s_score = 0,
    g_score = 0,
    overall_score = 0,
  } = scores;

  const confidencePercent = confidence?.confidence
    ? Math.round(confidence.confidence * 100)
    : null;

  return `
    <div class="score-card">
      <div class="score-pill e">
        <span style="color: #10B981;">●</span>
        E: ${formatScore(e_score)}
      </div>
      <div class="score-pill s">
        <span style="color: #3B82F6;">●</span>
        S: ${formatScore(s_score)}
      </div>
      <div class="score-pill g">
        <span style="color: #F59E0B;">●</span>
        G: ${formatScore(g_score)}
      </div>
      <div class="score-overall">${formatScore(overall_score)}/100</div>
      ${confidencePercent ? `<div class="confidence text-xs text-[#64748B]">置信度: ${confidencePercent}%</div>` : ''}
    </div>
  `;
}

/**
 * 创建单个维度的评分徽章
 * @param {string} dimension - 'E' | 'S' | 'G'
 * @param {number} score
 * @returns {string} - HTML 字符串
 */
export function createDimensionBadge(dimension, score) {
  const colors = {
    E: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10B981', dot: '●' },
    S: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3B82F6', dot: '●' },
    G: { bg: 'rgba(245, 158, 11, 0.15)', text: '#F59E0B', dot: '●' },
  };

  const color = colors[dimension] || colors.E;
  const label = {
    E: '环境',
    S: '社会',
    G: '治理',
  }[dimension] || '未知';

  return `
    <div class="score-pill" style="background-color: ${color.bg}; color: ${color.text}; border: 1px solid ${color.text}33;">
      <span>${color.dot}</span>
      ${label}: ${formatScore(score)}
    </div>
  `;
}

/**
 * 创建评分行 (用于报告等地方)
 * @param {Object} data - { e_score, s_score, g_score, overall_score, overall_trend }
 * @returns {string} - HTML 字符串
 */
export function createScoreRow(data) {
  const {
    e_score = 0,
    s_score = 0,
    g_score = 0,
    overall_score = 0,
    overall_trend = 'stable',
  } = data;

  const trendIcon = {
    up: '📈',
    down: '📉',
    stable: '➡️',
  }[overall_trend] || '➖';

  return `
    <div class="flex items-center gap-4 p-4 bg-[#1C2333] rounded-lg border border-[#2D3748]">
      <div class="flex-1">
        <div class="text-sm text-[#64748B] mb-1">综合评分</div>
        <div class="text-2xl font-bold" style="color: ${scoreColor(overall_score)};">
          ${formatScore(overall_score)}
          <span class="text-lg ml-2">${trendIcon}</span>
        </div>
        <div class="text-xs text-[#94A3B8] mt-1">${scoreLabel(overall_score)}</div>
      </div>

      <div class="flex gap-3">
        ${createDimensionBadge('E', e_score)}
        ${createDimensionBadge('S', s_score)}
        ${createDimensionBadge('G', g_score)}
      </div>
    </div>
  `;
}

/**
 * 创建迷你评分卡 (用于表格等紧凑显示)
 * @param {Object} scores
 * @returns {string}
 */
export function createMiniScoreCard(scores) {
  const { e_score = 0, s_score = 0, g_score = 0, overall_score = 0 } = scores;

  return `
    <div class="flex items-center gap-2" title="E: ${e_score}, S: ${s_score}, G: ${g_score}, Overall: ${overall_score}">
      <span class="inline-block w-5 h-5 rounded text-xs font-bold flex items-center justify-center"
            style="background-color: rgba(16, 185, 129, 0.2); color: #10B981;">E</span>
      <span class="text-xs font-mono">${formatScore(e_score)}</span>

      <span class="inline-block w-5 h-5 rounded text-xs font-bold flex items-center justify-center"
            style="background-color: rgba(59, 130, 246, 0.2); color: #3B82F6;">S</span>
      <span class="text-xs font-mono">${formatScore(s_score)}</span>

      <span class="inline-block w-5 h-5 rounded text-xs font-bold flex items-center justify-center"
            style="background-color: rgba(245, 158, 11, 0.2); color: #F59E0B;">G</span>
      <span class="text-xs font-mono">${formatScore(g_score)}</span>
    </div>
  `;
}
