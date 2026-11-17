import {requestJson,getDataMode} from './api.js';
import {html,escapeHtml as e,run} from './ui.js';
export async function loadTraces({room_id,run_id,devToken}) {
  const query = run_id ? '?run_id=' + encodeURIComponent(run_id) : '';
  const result = await requestJson('/api/dev/rooms/' + encodeURIComponent(room_id) + '/traces' + query,{headers:{'X-Dev-Token':devToken}});
  return result.runs;
}
