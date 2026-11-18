import {html,escapeHtml as e,money} from './ui.js';
import {displayPlan} from './plan.js';
import {agreementLabels,itemAgreement} from './agreement.js';
import {getUser} from './state.js';
export const sourceLinks = ids => ids.map((id,index) =>
  `<button class="source-link" type="button" data-message="${e(id)}">대화에서 보기${ids.length > 1 ? ' ' + (index + 1) : ''}</button>`
).join('');
export function renderItems(snapshot) {
  const plan = displayPlan(snapshot);
  html('items', snapshot.items.map(item => {
    const {state,counts} = itemAgreement(snapshot,item,plan);
    const label = state === 'confirmed' ? `확정 ✓ v${plan.plan_revision}` : agreementLabels[state];
    const stale = item.state === 'confirmed' && state !== 'confirmed' ? ' · 새 안 · 미확정' : '';
    return `<details class="card ${e(state)}"><summary>${e(item.title)} · ${e(label)}${stale}
      ${item.conflict_ids.length ? '<strong class="badge">! 충돌</strong>' : ''}</summary>
      <p>지지 기준 ${e(item.support_threshold)}명 · ${e(counts)} · v${e(item.item_version)}</p>
      ${sourceLinks(item.source_message_ids)}
    </details>`;
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
let lastConditionRoom;
let lastConditionValues;
export function renderConstraints(snapshot) {
  const previous = snapshot.room_id === lastConditionRoom ? lastConditionValues : null;
  const current = new Map();
  const active = [];
  const history = [];
  for (const item of snapshot.constraints) {
    const old = item.status === 'superseded';
    const value = JSON.stringify(item);
    current.set(item.id,value);
    const changed = !old && previous && previous.get(item.id) !== value;
    const input = conditionInput(item);
    const canEdit = !old && item.owner_id === getUser()?.id;
    const row = `<div class="card">
  <strong>${e(constraintLabels[item.key] ?? item.key)} · ${e(conditionValue(item))}</strong>
  ${changed ? '<span class="badge condition-change">최근 변경</span>' : ''}
  <p class="constraint-meta">${e(memberName(snapshot,item.owner_id))} · ${item.kind === 'hard' ? '필수' : '선호'} · ${e(constraintStatuses[item.status] ?? item.status)}</p>
  ${sourceLinks(item.source_message_ids)}
  ${canEdit ? `<details class="card-details"><summary>조건 수정</summary>
    <form data-constraint="${e(item.id)}" data-value-mode="${input ? 'scalar' : 'json'}">
      ${input || `<label>값 (JSON)<input name="value" value="${e(JSON.stringify(item.value))}" required></label>`}
      <button>수정 저장</button>
    </form>
  </details>` : ''}
  ${canEdit && item.status === 'needs_owner_confirmation' ? `<button type="button" data-constraint-confirm="${e(item.id)}">본인 확인</button>` : ''}</div>`;
    (old ? history : active).push(row);
  }
  html('constraints', (active.join('') || '<p>아직 등록된 조건이 없습니다.</p>') +
    (history.length ? `<details class="card-details"><summary>이전 조건 보기</summary>${history.join('')}</details>` : ''));
  lastConditionRoom = snapshot.room_id;
  lastConditionValues = current;
}
const conflictLabels = {time:'시간',budget:'예산',opening_hours:'영업시간',personal_constraint:'개인 조건',preference:'선호'};
export function renderConflicts(snapshot) {
  const cards = snapshot.conflicts.filter(item => item.status === 'open').map(item => `<div class="card conflict">
    <strong>! ${e(conflictLabels[item.type] ?? item.type)} · ${item.blocking ? '확정 차단' : '선호 선택'}</strong>
    <p>${e(item.explanation)}</p>
    <ul class="decision-options">${item.options.map(option => `<li>
      <button type="button" data-conflict="${e(item.id)}" data-option="${e(option.id)}" ${option.requires_owner_id && option.requires_owner_id !== getUser()?.id ? 'disabled' : ''}>${e(option.label)}</button>
      <p>${e(option.effect_summary)}${option.requires_owner_id ? ' · ' + e(memberName(snapshot,option.requires_owner_id)) + ' 본인만 선택 가능' : ''}</p></li>`).join('')}</ul>
  </div>`).join('');
  html('conflicts', cards ? '<h3 class="card-section-title">해결할 충돌</h3>' + cards : '');
}
const fieldValue = field => field.type === 'number' ? field.valueAsNumber : field.value.trim();
export function readDecisionValue(form) {
  const mode = form.dataset.valueMode;
  if (mode === 'scalar') return fieldValue(form.elements.value);
  if (mode === 'route-departure') {
    const value = form.elements.value.value;
    if (!value) throw new Error('한국 시간 기준 출발 날짜와 시각을 입력해 주세요.');
    const timestamp = value.length === 16 ? value + ':00' : value;
    const departure = timestamp + '+09:00';
    if (!Number.isFinite(Date.parse(departure)) || Date.parse(departure) <= Date.now()) {
      throw new Error('한국 시간 기준 미래의 출발 날짜와 시각을 입력해 주세요.');
    }
    return {value:departure};
  }
  if (mode === 'target-places') {
    const place_ref = form.elements.place_ref?.value;
    if (place_ref) return {target_names:[],place_ref};
    const target_names = form.elements.target_names.value.split(',').map(name => name.trim()).filter(Boolean);
    if (!target_names.length) throw new Error('장소를 선택하거나 장소명을 입력해 주세요.');
    return {target_names};
  }
  if (mode !== 'fields') return JSON.parse(form.elements.value.value);
  const fields = Array.from(form.elements).filter(field => field.name);
  return Object.fromEntries(fields.map(field => [field.name,fieldValue(field)]));
}
export function parseValue(value) {
  try { return JSON.parse(value); }
  catch { return value; }
}
export function readAnswer(field,data) {
  if (field === 'constraint_value') return {value:parseValue(data.value)};
  const numeric = new Set(['quantity','stay_minutes','latitude','longitude']);
  return Object.fromEntries(Object.entries(data).map(([key,value]) => [key,numeric.has(key) ? Number(value) : value]));
}
export function placeRefOf(snapshot,id) {
  return snapshot.current_plan?.item_snapshots.find(item => item.id === id)?.place_ref ?? null;
}
const anchorFields = `<label>이름<input name="label" required></label>
  <label>위도<input name="latitude" type="number" min="-90" max="90" step="any" required></label>
  <label>경도<input name="longitude" type="number" min="-180" max="180" step="any" required></label>`;
const questionFields = {
  origin: anchorFields,
  destination: anchorFields,
  lodging: anchorFields,
  region: '<label>여행 지역<input name="value" type="text" required pattern=".*\\S.*"></label>',
  route_departure: '<label>출발 시각 (한국 시간 · UTC+09:00)<input type="datetime-local" name="value" required></label>',
  menu_selection: `<label>메뉴 ID<input name="menu_id" required></label>
    <small>장소 카드의 정보 출처에서 메뉴 ID를 확인할 수 있어요.</small>
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
function targetPlaceFields(question) {
  const options = (question.place_choices ?? []).map(({place_ref,name,address}) =>
    `<option value="${e(place_ref)}">${e(name)}${address ? ` · ${e(address)}` : ''}</option>`).join('');
  return `${options ? `<label>조회된 장소<select name="place_ref"><option value="">직접 장소명 입력</option>${options}</select></label>` : ''}
    <label>장소명 (여러 곳이면 쉼표로 구분)<input name="target_names" ${options ? '' : 'required'}></label>`;
}
const questionLabels = {origin:'출발지',destination:'귀가지',lodging:'숙소',region:'여행 지역',route_departure:'경로 조회 시각',menu_selection:'메뉴 선택',visit_duration:'체류시간',constraint_value:'조건 확인',support_target:'의견 대상',target_places:'조회할 장소'};
const questionModes = {target_places:'target-places',route_departure:'route-departure'};
export function renderQuestions(snapshot) {
  const cards = snapshot.questions.filter(question => question.status === 'open').map(question => {
    const targetPlaces = question.field === 'target_places';
    let fields = question.field === 'support_target'
      ? supportFields(snapshot.items,question.related_item_ids)
      : targetPlaces ? targetPlaceFields(question) : questionFields[question.field];
    if (['origin','destination','lodging'].includes(question.field)) fields = `<fieldset data-anchor-picker="${e(question.field)}"><legend>${e(questionLabels[question.field])}</legend>${fields}<button type="button" class="ghost sm" data-clear-anchor>입력 지우기</button></fieldset>`;
    if (question.field === 'menu_selection') {
      const ref = placeRefOf(snapshot,question.target_ref);
      if (ref) fields = fields.replace('<input name="menu_id" required>',`<select name="menu_id" required data-menu-place="${e(ref)}"><option value="">메뉴 불러오는 중…</option></select>`);
    }
    const condition = question.field === 'constraint_value'
      ? snapshot.constraints.find(item => item.id === question.target_ref)
      : null;
    const input = fields || conditionInput(condition);
    const mode = questionModes[question.field] ?? (input ? 'fields' : 'json');
    const owner = question.owner_id;
    const canAnswer = !owner || owner === getUser()?.id;
    const subject = condition ? constraintLabels[condition.key] ?? condition.key
      : snapshot.items.find(item => item.id === question.target_ref)?.title ?? questionLabels[question.field] ?? '추가 입력';
    return `<div class="card"><strong>${e(question.text)}</strong><p class="constraint-meta">${e(subject)} · ${owner ? e(memberName(snapshot,owner)) : '공유 질문'}</p>
  ${canAnswer ? `<form data-question="${e(question.id)}" data-value-mode="${mode}">${input || `<label>응답 (JSON)<textarea name="value" required>${e(JSON.stringify(answerExamples[question.field]))}</textarea></label>`}<button>답변 보내기</button></form>` : ''}</div>`;
  }).join('');
  html('questions', cards ? '<h3 class="card-section-title">확인 질문</h3>' + cards : '');
}
