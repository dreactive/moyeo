import {displayPlan} from './plan.js';
import {escapeHtml as e,html} from './ui.js';

export function renderRoutePanel(snapshot, date) {
  const days = displayPlan(snapshot)?.days ?? [];
  const selected = days.find(day => day.date === date) ?? days[0];
  html('route-days', days.map((day,index) => `<button type="button" aria-pressed="${day === selected}" data-day="${e(day.date)}" title="${e(day.date)}">${index + 1}일차</button>`).join(''));
}
