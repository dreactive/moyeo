import {displayPlan} from './plan.js';
import {escapeHtml as e,html} from './ui.js';

export function renderRoutePanel(snapshot, date) {
  const plan = displayPlan(snapshot);
  const days = plan?.days ?? [];
  const selected = days.find(day => day.date === date) ?? days[0];
  html('route-days', days.map((day,index) => `<button type="button" aria-pressed="${day === selected}" data-day="${e(day.date)}" title="${e(day.date)}">${index + 1}일차</button>`).join(''));
  html('route-summary', selected ? visitList(selected.visits,plan.item_snapshots) : '');
}

function visitList(visits, items) {
  if (!visits.length) return '<p class="muted">이 날에 예정된 방문이 없어요.</p>';
  const titles = new Map(items.map(item => [item.id,item.title]));
  return `<ol>${visits.map(visit => `<li><button type="button" data-place="${e(visit.place_ref)}">${e(titles.get(visit.item_id) ?? visit.place_ref)}</button></li>`).join('')}</ol>`;
}
