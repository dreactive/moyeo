import {html,escapeHtml as e} from './ui.js';
import {displayPlan,sameTarget} from './plan.js';
import {getUser} from './state.js';
const labels = {mentioned:'언급됨',supported:'다수 지지',confirmed:'확정',pending:'새 안 · 미확정'};
export const sourceLinks = ids => ids.map(id => `<button data-message="${e(id)}">근거 ${e(id)}</button>`).join('');
export function renderItems(snapshot) {
  const plan = displayPlan(snapshot);
  html('items', snapshot.items.map(item => {
    const confirmed = item.state === 'confirmed' && item.included_in_plan && sameTarget(plan?.confirmation_target,snapshot.confirmed_plan?.confirmation_target) && plan.item_snapshots.some(old => old.id === item.id && old.item_version === item.item_version);
    const state = item.state === 'confirmed' && !confirmed ? 'pending' : item.state;
    return `<div class="card ${e(state)}"><strong>${e(item.title)} · ${e(labels[state])}</strong>
    ${item.conflict_ids.length ? '<strong class="badge">! 충돌</strong>' : ''}
    <p>지지 ${item.supporter_ids.length}명 / 기준 ${item.support_threshold}명 · v${item.item_version}</p>${sourceLinks(item.source_message_ids)}</div>`;
  }).join('') || '<p>아직 공동 항목이 없습니다.</p>');
}
export function renderConstraints(snapshot) {
  html('constraints', snapshot.constraints.map(item => `<div class="card">
  <strong>${e(item.owner_id)} · ${e(item.kind)} · ${e(item.key)}</strong><p>${e(JSON.stringify(item.value))} · ${e(item.status)}</p>
  ${sourceLinks(item.source_message_ids)}
  ${item.owner_id === getUser()?.id ? `<form data-constraint="${e(item.id)}"><label>값 (JSON)<input name="value" value="${e(JSON.stringify(item.value))}" required></label><button>수정</button><button type="button" data-constraint-confirm="${e(item.id)}">본인 확인</button></form>` : '<p>소유자만 수정·확인할 수 있습니다.</p>'}</div>`).join(''));
}
export function renderConflicts(snapshot) {
  html('conflicts', snapshot.conflicts.filter(item => item.status === 'open').map(item => `<div class="card conflict"><h3>! ${e(item.type)} · ${item.blocking ? '확정 차단' : '선호 선택'}</h3><p>${e(item.explanation)}</p>${item.options.map(option => `<p><button data-conflict="${e(item.id)}" data-option="${e(option.id)}" ${option.requires_owner_id && option.requires_owner_id !== getUser()?.id ? 'disabled' : ''}>${e(option.label)}</button> ${e(option.effect_summary)} · ${option.requires_owner_id ? e(option.requires_owner_id) + ' 본인 조건 수정·확인 필요' : '새 초안 생성'}</p>`).join('')}</div>`).join(''));
}
const answerExamples = {
  origin:{label:'출발지',latitude:34.76,longitude:127.66},
  destination:{label:'귀가지',latitude:34.76,longitude:127.66},
  lodging:{label:'숙소',latitude:34.75,longitude:127.67},
  menu_selection:{menu_id:'',quantity:1,scope:'shared'},
  visit_duration:{stay_minutes:60},constraint_value:{value:''},support_target:{item_id:''}
};
export function renderQuestions(snapshot) {
  html('questions', snapshot.questions.filter(question => question.status === 'open').map(question => `<div class="card"><h3>${e(question.text)}</h3><p>${e(question.field)} / 대상 ${e(question.target_ref)} / ${e(question.owner_id ?? '공유 질문')}</p>
  <form data-question="${e(question.id)}"><label>응답 (JSON · 메뉴 수량/공유·체류시간 등)<textarea name="value" required>${e(JSON.stringify(answerExamples[question.field]))}</textarea></label><button ${question.owner_id && question.owner_id !== getUser()?.id ? 'disabled' : ''}>답변 보내기</button></form></div>`).join(''));
}
