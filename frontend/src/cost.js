import {html,escapeHtml as e,money} from './ui.js';
import {displayPlan,planAgreement} from './plan.js';
import {currentAgentResults,resultBasis} from './agent-results.js';
const userColumns = {per_person_krw:'1인 전체 계획액',paid_by_user_krw:'개인 기지출',remaining_budget_krw:'앞으로 쓸 수 있는 금액',planned_balance_krw:'계획 반영 후 여유'};
const costGroup = {intercity_transport:'transport',car:'transport',lodging:'lodging',meal:'meal',admission:'admission',other:'other'};
const categoryLabels = {transport:'교통',lodging:'숙박',meal:'식사',admission:'입장·체험',other:'기타'};
const scopeLabels = {shared:'공동 분담',per_person:'1인 기준'};
function costComposition(cost) {
  if (!cost.total_krw || cost.unknown_line_count) return '';
  const groups = new Map();
  for (const line of cost.lines) {
    if (line.subtotal_krw == null) return '';
    const group = costGroup[line.category] ?? 'other';
    groups.set(group,(groups.get(group) ?? 0) + line.subtotal_krw);
  }
  const entries = [...groups];
  return `<div class="cost-composition-bar" role="img" aria-label="방 전체 경비 구성">
    ${entries.map(([group,amount]) => `<span data-category="${group}" style="flex-grow:${amount}"></span>`).join('')}
  </div><ul class="cost-composition-legend">
    ${entries.map(([group,amount]) => `<li data-category="${group}">${categoryLabels[group]} ${money(amount)}</li>`).join('')}
  </ul>`;
}
export function renderCost(cost,userId,members = [],snapshot) {
  const plan = snapshot && displayPlan(snapshot);
  const agreement = plan && planAgreement(snapshot,plan);
  const context = agreement ? `<p class="consensus-status ${agreement.official ? 'official' : 'pending'}">여행안 v${e(plan.plan_revision)} · ${agreement.status} · 같은 여행안 동의 ${agreement.count}/${members.length}</p>` : '';
  const results = currentAgentResults(snapshot);
  const partial = results?.calculate_costs;
  const partialMarkup = partial ? `<details class="card-details" id="agent-cost" ${cost ? '' : 'open'}>
    <summary>부분 비용 계산</summary>${resultBasis(results)}${costContent(partial,userId,members)}</details>` : '';
  html('cost',`${context}${cost ? costContent(cost,userId,members) : partial ? '' : '경비 미확인'}${partialMarkup}`);
}
function costContent(cost,userId,members) {
  const names = new Map(members.map(({user_id,name}) => [user_id,name]));
  const personal = userId ? `<p class="personal-cost">내 전체 계획액 <strong class="cost-amount">${money(cost.per_person_krw[userId])}</strong></p>` : '';
  const budget = userId ? `<dl class="card-facts">
    <dt>내 기지출</dt><dd>${money(cost.paid_by_user_krw[userId])}</dd>
    <dt>앞으로 쓸 수 있는 금액</dt><dd>${money(cost.remaining_budget_krw[userId])}</dd>
    <dt>계획 반영 후 여유</dt><dd>${money(cost.planned_balance_krw[userId])}</dd>
  </dl>` : '';
  return `${personal}${budget}<p>방 전체 계획액 <strong>${money(cost.total_krw)}</strong> · 알려진 소계 ${money(cost.known_total_krw)} · 전체 기지출 ${money(cost.paid_krw)}</p>
  <p>미확인 ${e(cost.unknown_line_count)}건 · 추정 ${e(cost.estimated_line_count)}건</p>
  ${costComposition(cost)}
  <details class="card-details"><summary>참가자별 경비</summary>
  ${Object.keys(cost.per_person_krw).map(id => `<p><strong>${e(names.get(id) ?? id)}</strong></p>
    <dl class="card-facts">${Object.entries(userColumns).map(([key,label]) => `<dt>${label}</dt><dd>${money(cost[key][id])}</dd>`).join('')}</dl>`).join('')}
  </details>
  <details class="card-details"><summary>방 전체 비용 내역</summary>
  ${cost.lines.map(line => `<div class="card"><strong>${e(line.description)}</strong><p>${e(categoryLabels[costGroup[line.category]] ?? line.category)} · ${e(scopeLabels[line.scope] ?? line.scope)} · ${e(names.get(line.owner_id) ?? line.owner_id ?? '전체')} · ${line.paid ? '기지출' : '예정'}</p><p>단가 ${money(line.unit_price_krw)} × 수량 ${e(line.quantity)} · 방 전체 소계 ${money(line.subtotal_krw)}</p><p>가정 ${e(line.assumption ?? '없음')} · 근거 ${e(line.evidence_id ?? '사용자 입력/미확인')}</p></div>`).join('') || '<p>등록된 비용이 없습니다.</p>'}
  </details>`;
}
