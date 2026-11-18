import {html,escapeHtml as e,money} from './ui.js';
const userColumns = {per_person_krw:'1인 전체 계획액',paid_by_user_krw:'개인 기지출',remaining_budget_krw:'앞으로 쓸 수 있는 금액',planned_balance_krw:'계획 반영 후 여유'};
export function renderCost(cost,userId) {
  if (!cost) return html('cost','경비 미확인');
  const personal = userId ? `<p class="personal-cost">내 전체 계획액 <strong class="cost-amount">${money(cost.per_person_krw[userId])}</strong></p>` : '';
  const budget = userId ? `<dl class="card-facts">
    <dt>내 기지출</dt><dd>${money(cost.paid_by_user_krw[userId])}</dd>
    <dt>앞으로 쓸 수 있는 금액</dt><dd>${money(cost.remaining_budget_krw[userId])}</dd>
    <dt>계획 반영 후 여유</dt><dd>${money(cost.planned_balance_krw[userId])}</dd>
  </dl>` : '';
  html('cost', `${personal}${budget}<p>방 전체 계획액 <strong>${money(cost.total_krw)}</strong> · 알려진 소계 ${money(cost.known_total_krw)} · 전체 기지출 ${money(cost.paid_krw)}</p>
  <p>미확인 ${cost.unknown_line_count}건 · 추정 ${cost.estimated_line_count}건</p>
  <table><thead><tr><th>참가자</th>${Object.values(userColumns).map(label => `<th>${label}</th>`).join('')}</tr></thead><tbody>
  ${Object.keys(cost.per_person_krw).map(id => `<tr><th>${e(id)}</th>${Object.keys(userColumns).map(key => `<td>${money(cost[key][id])}</td>`).join('')}</tr>`).join('')}</tbody></table>
  ${cost.lines.map(line => `<div class="card"><strong>${e(line.description)}</strong><p>${e(line.category)} / ${e(line.scope)} / ${e(line.owner_id ?? '전체')} · ${line.paid ? '기지출' : '예정'}</p><p>단가 ${money(line.unit_price_krw)} × 수량 ${e(line.quantity)} · 방 전체 소계 ${money(line.subtotal_krw)}</p><p>가정: ${e(line.assumption ?? '없음')} · 근거 ${e(line.evidence_id ?? '사용자 입력/미확인')}</p></div>`).join('')}`);
}
