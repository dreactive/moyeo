import {requestJson,getDataMode} from './api.js';
import {html,escapeHtml as e,run} from './ui.js';
export async function loadTraces({room_id,run_id,devToken}) {
  const query = run_id ? '?run_id=' + encodeURIComponent(run_id) : '';
  const result = await requestJson('/api/dev/rooms/' + encodeURIComponent(room_id) + '/traces' + query,{headers:{'X-Dev-Token':devToken}});
  return result.runs;
}
export function renderTraces(runs) {
  html('traces',runs.map(run => `<section class="panel"><h2>Run ${e(run.run_id)}</h2><p>${e(run.room_id)} · ${e(run.started_at)}</p>
  ${run.events.map(event => `<div class="card"><strong>step ${event.step} / ${e(event.event)} / call ${e(event.call_id ?? '없음')}</strong><p>${e(event.created_at)}</p><pre>${e(JSON.stringify(event.payload,null,2))}</pre></div>`).join('')}</section>`).join('') || '<p>조회된 run이 없습니다.</p>');
}
if (typeof document !== 'undefined') {
  html('mode',getDataMode() === 'fixture' ? '개발용 fixture · 실제 API/Qwen/접근제한 검증 아님' : 'LIVE · 개발자 전용 API');
  document.getElementById('trace-form').onsubmit = event => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    event.target.elements.devToken.value = '';
    html('traces','조회 중…');
    html('error','');
    run(async () => renderTraces(await loadTraces(data)));
  };
}
