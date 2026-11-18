const rendered = new Map();
export function renderChanged(key,value,render) {
  const stamp = JSON.stringify(value);
  if (rendered.get(key) === stamp) return;
  if (render() !== false) rendered.set(key,stamp);
}
export function roomMeta(config) {
  const nights = Math.round((Date.parse(config.end_date) - Date.parse(config.start_date)) / 86400000);
  return `${config.start_date} — ${config.end_date} · ${nights}박 ${nights + 1}일 · ${config.region}`;
}
import {html,escapeHtml as e} from './ui.js';
import {sourceLinks} from './items.js';
import {currentAgentResults,resultBasis} from './agent-results.js';
import {chatDate,chatTime} from './chat.js';
export function renderOverview(snapshot) {
  html('room-heading',e(snapshot.title));
  html('room-meta',e(roomMeta(snapshot.config)));
  html('invite-code',e(snapshot.invite_code));
  html('members',snapshot.members.map(member => `<span class="member-avatar" title="${e(member.name)}">${e(member.name.slice(0,1))}</span>`).join('') + `<span class="member-count">${snapshot.members.length}명 참여</span>`);
}
const agentLabels = {idle:'여행 이야기를 기다리고 있어요',running:'조건과 동선을 검토하고 있어요',needs_input:'확인이 필요한 내용이 있어요',done:'여행안 검토가 끝났어요',
  waiting:'아직 완료되지 않은 작업이 있어요',failed:'일부 작업을 완료하지 못했어요',held:'최신 내용에 맞춰 작업을 다시 확인하는 중이에요'};
const requestLabels = {needs_context:'요청 문맥 확인 필요',needs_input:'답변 필요',pending:'조회 대기',resolved:'조회 대상 확인됨',
  completed:'완료',cancelled:'취소됨',superseded:'새 요청으로 변경됨',unsupported:'지원하지 않는 요청',failed:'조회 실패'};
const lookupFields = {price:'가격',opening_hours:'영업시간',location:'위치',details:'상세 정보'};
function requestProgress(snapshot) {
  const requests = snapshot.agent_requests ?? [];
  if (!requests.length) return '';
  const messages = new Map(snapshot.messages.map(message => [message.id,message]));
  const names = new Map([snapshot.confirmed_plan,snapshot.current_plan,snapshot.review_plan]
    .flatMap(plan => plan?.item_snapshots ?? []).map(item => [item.place_ref,item.title]));
  return `<details class="card-details" open><summary>요청별 진행 상태</summary><ul class="agent-requests">${requests.map(request => {
    const message = messages.get(request.source_message_id);
    const owner = snapshot.members.find(member => member.user_id === request.owner_id)?.name;
    const completed = request.completed_target_names?.length || request.completed_refs?.length || 0;
    const failures = request.failed_targets ?? [];
    const unresolved = ['cancelled','superseded'].includes(request.status) ? [] : (request.unresolved_target_names ?? [])
      .filter(name => !failures.some(f => f.target_name === name));
    const pending = (request.pending_refs ?? []).filter(ref => !failures.some(f => f.target_ref === ref)).length + unresolved.length;
    const results = (request.result_refs ?? []).map(ref => {
      const knownPlace = !ref.startsWith('anchor:')
        && (names.has(ref) || request.target_refs?.includes(ref) || /^(?:fixture:place-[^:]+|kakao:\d+)$/.test(ref));
      return knownPlace ? `<button type="button" data-place="${e(ref)}">${e(names.get(ref) ?? ref)}</button>` : `<code>${e(ref)}</code>`;
    }).join(' ');
    const targets = request.target_names?.join(', ');
    const excluded = request.excluded_names?.join(', ');
    const missing = request.missing_fields?.map(field => lookupFields[field] ?? field).join(', ');
    return `<li><strong>${e(requestLabels[request.status] ?? request.status)}</strong>${owner ? ` · ${e(owner)}` : ''}
      ${request.evidence?.quote ? `<p>“${e(request.evidence.quote)}”</p>` : ''}
      ${targets || excluded ? `<p>${targets ? `대상 ${e(targets)}` : ''}${targets && excluded ? ' · ' : ''}${excluded ? `제외 ${e(excluded)}` : ''}</p>` : ''}
      ${completed || pending ? `<p>완료 ${completed}곳 · 대기 ${pending}곳</p>` : ''}
      ${unresolved.length ? `<p>대상 미확인 ${e(unresolved.join(', '))}</p>` : ''}
      ${missing ? `<p>정보 미확인 ${e(missing)}</p>` : ''}
      ${request.response ? `<p class="agent-response">${e(request.response)}</p>` : ''}
      ${failures.map(f => `<p class="muted">${e(f.target_name || f.target_ref || f.tool_name)} · 조회 실패 · ${e(f.error_code)}</p>`).join('')}
      ${request.error_code && !failures.length ? `<p class="muted">오류 ${e(request.error_code)}</p>` : ''}
      ${results ? `<div>결과 ${results}</div>` : ''}
      ${request.source_message_id ? sourceLinks([request.source_message_id]) : ''}
      ${message?.created_at ? `<time datetime="${e(message.created_at)}">${e(chatDate(message.created_at))} ${e(chatTime(message.created_at))}</time>` : ''}
    </li>`;
  }).join('')}</ul></details>`;
}
function latestCalculations(snapshot) {
  const results = snapshot.agent_results;
  if (!results?.build_itinerary && !results?.calculate_costs) return '';
  if (!currentAgentResults(snapshot)) return `<p>${resultBasis(results,true)}</p>`;
  return `<p>${resultBasis(results)}
    ${results.build_itinerary ? '<a href="#agent-itinerary">부분 일정 보기</a>' : ''}
    ${results.calculate_costs ? '<a href="#agent-cost">부분 비용 보기</a>' : ''}</p>`;
}
export function renderAgentBanner(snapshot) {
  const status = snapshot.agent_status;
  const label = status.label === status.state || status.label === 'Ready' ? agentLabels[status.state] ?? status.state : status.label;
  const questions = snapshot.questions.filter(item => item.status === 'open').length;
  const conflicts = snapshot.conflicts.filter(item => item.status === 'open').length;
  html('agent',`<strong>${e(label)}</strong><p>확인 질문 ${questions}개 · 해결할 충돌 ${conflicts}개</p>${requestProgress(snapshot)}${latestCalculations(snapshot)}`);
  const button = document.getElementById('replan');
  button.disabled = snapshot.agent_status.state === 'running' || button.dataset?.pending === 'true';
}
import {displayPlan} from './plan.js';
import {locatedMentions} from './map.js';
export const routeKey = (snapshot,date) => {
  const plan = displayPlan(snapshot);
  return JSON.stringify([snapshot.room_id,plan?.confirmation_target,snapshot.config,date,
    locatedMentions(snapshot,plan).map(m => [m.id,m.ref,m.unplaced])]);
};
export function placeVisitDay(plan,ref,selected) {
  const contains = day => day.visits.some(visit => visit.place_ref === ref);
  return plan?.days.find(day => day.date === selected && contains(day)) ?? plan?.days.find(contains);
}
export function sharedRenderData({messages,agent_status,seq,...shared}) { return shared; }
