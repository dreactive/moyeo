import {html,escapeHtml as e,money} from './ui.js';
import {displayPlan,sameTarget,hasCurrentBasis} from './plan.js';
import {getUser} from './state.js';
const labels = {mentioned:'언급됨',supported:'다수 지지',confirmed:'확정',pending:'새 안 · 미확정'};
export const sourceLinks = ids => ids.map(id => `<button data-message="${e(id)}">근거 ${e(id)}</button>`).join('');
export function renderItems(snapshot) {
  const plan = displayPlan(snapshot);
  html('items', snapshot.items.map(item => {
    const official = snapshot.confirmed_plan;
    const matchesItem = entry => entry.id === item.id && entry.item_version === item.item_version;
    const confirmed = sameTarget(plan?.confirmation_target,official?.confirmation_target)
      && hasCurrentBasis(snapshot,plan.confirmation_target)
      && plan.selected_item_ids.includes(item.id) && official.selected_item_ids.includes(item.id)
      && plan.item_snapshots.some(matchesItem) && official.item_snapshots.some(matchesItem);
    const state = confirmed ? 'confirmed' : item.state === 'confirmed' ? 'pending' : item.state;
    return `<div class="card ${e(state)}"><strong>${e(item.title)} · ${e(labels[state])}</strong>
    ${item.conflict_ids.length ? '<strong class="badge">! 충돌</strong>' : ''}
    <p>지지 ${item.supporter_ids.length}명 / 기준 ${item.support_threshold}명 · v${item.item_version}</p>${sourceLinks(item.source_message_ids)}</div>`;
  }).join('') || '<p>아직 공동 항목이 없습니다.</p>');
}
const constraintLabels = {budget:'1인 예산',budget_krw:'1인 예산',return_by:'귀가지 도착 제한',allergy:'알레르기',diet:'식이 조건'};
const constraintStatuses = {needs_owner_confirmation:'본인 확인 필요',confirmed:'본인 확인됨',superseded:'이전 조건'};
function conditionValue({key,value}) {
  if (constraintLabels[key] === '1인 예산' && typeof value === 'number') return money(value);
  return value && typeof value === 'object' ? JSON.stringify(value) : value ?? '미확인';
}
function conditionInput(condition) {
  const type = {budget:'number',budget_krw:'number',return_by:'time'}[condition?.key];
  if (!type) return '';
  return `<label>${constraintLabels[condition.key]}<input name="value" type="${type}" value="${e(condition.value)}" required></label>`;
}
const memberName = (snapshot,id) => snapshot.members.find(member => member.user_id === id)?.name ?? id;
export function renderConstraints(snapshot) {
  const active = [];
  const history = [];
  for (const item of snapshot.constraints) {
    const old = item.status === 'superseded';
    const input = conditionInput(item);
    const row = `<div class="card">
  <strong>${e(constraintLabels[item.key] ?? item.key)} · ${e(conditionValue(item))}</strong>
  <p class="constraint-meta">${e(memberName(snapshot,item.owner_id))} · ${item.kind === 'hard' ? '필수' : '선호'} · ${e(constraintStatuses[item.status] ?? item.status)}</p>
  ${sourceLinks(item.source_message_ids)}
  ${!old && item.owner_id === getUser()?.id ? `<form data-constraint="${e(item.id)}" data-value-mode="${input ? 'scalar' : 'json'}">${input || `<label>값 (JSON)<input name="value" value="${e(JSON.stringify(item.value))}" required></label>`}<button>수정</button>
  ${item.status === 'needs_owner_confirmation' ? `<button type="button" data-constraint-confirm="${e(item.id)}">본인 확인</button>` : ''}</form>` : ''}</div>`;
    (old ? history : active).push(row);
  }
  html('constraints', (active.join('') || '<p>아직 등록된 조건이 없습니다.</p>') +
    (history.length ? `<details class="card-details"><summary>이전 조건 보기</summary>${history.join('')}</details>` : ''));
}
export function renderConflicts(snapshot) {
  html('conflicts', snapshot.conflicts.filter(item => item.status === 'open').map(item => `<div class="card conflict"><h3>! ${e(item.type)} · ${item.blocking ? '확정 차단' : '선호 선택'}</h3><p>${e(item.explanation)}</p>${item.options.map(option => `<p><button data-conflict="${e(item.id)}" data-option="${e(option.id)}" ${option.requires_owner_id && option.requires_owner_id !== getUser()?.id ? 'disabled' : ''}>${e(option.label)}</button> ${e(option.effect_summary)} · ${option.requires_owner_id ? e(option.requires_owner_id) + ' 본인 조건 수정·확인 필요' : '새 초안 생성'}</p>`).join('')}</div>`).join(''));
}
const fieldValue = field => field.type === 'number' ? field.valueAsNumber : field.value.trim();
export function readDecisionValue(form) {
  const mode = form.dataset.valueMode;
  if (mode === 'scalar') return fieldValue(form.elements.value);
  if (mode !== 'fields') return JSON.parse(form.elements.value.value);
  const fields = Array.from(form.elements).filter(field => field.name);
  return Object.fromEntries(fields.map(field => [field.name,fieldValue(field)]));
}
const anchorFields = `<label>이름<input name="label" required></label>
  <label>위도<input name="latitude" type="number" min="-90" max="90" step="any" required></label>
  <label>경도<input name="longitude" type="number" min="-180" max="180" step="any" required></label>`;
const questionFields = {
  origin: anchorFields,
  destination: anchorFields,
  lodging: anchorFields,
  menu_selection: `<label>메뉴 ID<input name="menu_id" required></label>
    <label>수량<input name="quantity" type="number" min="0" step="any" value="1" required></label>
    <label>분담 방식<select name="scope"><option value="shared">함께 나누기</option><option value="per_person">각자 주문</option></select></label>`,
  visit_duration: '<label>체류시간 (분)<input name="stay_minutes" type="number" min="1" step="1" required></label>'
};
const answerExamples = {constraint_value:{value:''}};
function supportFields(items,relatedIds) {
  const options = items.filter(item => !relatedIds.length || relatedIds.includes(item.id))
    .map(item => `<option value="${e(item.id)}">${e(item.title)}</option>`).join('');
  return `<label>의견 대상<select name="item_id" required><option value="">항목을 선택해 주세요</option>${options}</select></label>`;
}
export function renderQuestions(snapshot) {
  html('questions', snapshot.questions.filter(question => question.status === 'open').map(question => {
    const fields = question.field === 'support_target'
      ? supportFields(snapshot.items,question.related_item_ids)
      : questionFields[question.field];
    const condition = question.field === 'constraint_value'
      ? snapshot.constraints.find(item => item.id === question.target_ref)
      : null;
    const input = fields || conditionInput(condition);
    return `<div class="card"><h3>${e(question.text)}</h3><p>${e(question.field)} / 대상 ${e(question.target_ref)} / ${e(question.owner_id ?? '공유 질문')}</p>
  <form data-question="${e(question.id)}" data-value-mode="${input ? 'fields' : 'json'}">${input || `<label>응답 (JSON)<textarea name="value" required>${e(JSON.stringify(answerExamples[question.field]))}</textarea></label>`}<button ${question.owner_id && question.owner_id !== getUser()?.id ? 'disabled' : ''}>답변 보내기</button></form></div>`;
  }).join(''));
}
