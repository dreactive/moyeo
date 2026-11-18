import {escapeHtml as e} from './ui.js';
import {agreementMarkup} from './agreement.js';

const versionLabels = {participant_version:'참가자',constraint_version:'조건',evidence_version:'관측',plan_revision:'여행안'};

export function currentAgentResults(snapshot) {
  const results = snapshot?.agent_results;
  return results && Object.keys(versionLabels).every(key => Number.isInteger(results.versions?.[key])
    && results.versions[key] === snapshot.versions?.[key]) ? results : undefined;
}

export function resultBasis({run_id,versions},previous = false) {
  const basis = Object.entries(versionLabels).map(([key,label]) => `${label} ${versions?.[key] == null ? '미확인' : `v${e(versions[key])}`}`);
  return `<small class="result-basis">실행 ${e(run_id)} · ${previous ? '이전 입력 기준' : '입력 기준'} · ${basis.join(' · ')} · 미확정</small>`;
}

const observationFields = {route:'경로',opening_hours:'영업시간',location:'위치',price:'가격'};
const reasons = {missing_route:'경로 미조회',unresolved_place:'장소 미확인',outside_trip_dates:'여행 날짜 밖'};
export function itineraryGaps(result,items,config,agreements) {
  const names = new Map(items.flatMap(item => [[item.id,item.title],...(item.place_ref ? [[item.place_ref,item.title]] : [])]));
  for (const [key,label] of Object.entries({origin:'출발지',lodging:'숙소',destination:'귀가지'})) {
    names.set(`anchor:${key}`,config[key]?.label ?? label);
  }
  for (const {item_id,place_ref} of result.unplaced_items ?? []) {
    if (place_ref && names.has(item_id)) names.set(place_ref,names.get(item_id));
  }
  const title = (id,ref) => names.get(id) ?? names.get(ref) ?? ref ?? id;
  const unplaced = (result.unplaced_items ?? []).map(({item_id,place_ref,reason}) => {
    const name = e(title(item_id,place_ref));
    const subject = place_ref ? `<button type="button" data-place="${e(place_ref)}">${name}</button>` : name;
    return `<li>${subject} · ${e(reasons[reason] ?? reason)}
      ${agreements ? agreementMarkup(agreements.get(item_id)) : ''}</li>`;
  }).join('');
  const missing = (result.missing_observations ?? []).map(({field,place_ref,item_id,from_ref,to_ref,date,departure_at,reason}) => {
    const subject = from_ref && to_ref ? `${title(null,from_ref)} → ${title(null,to_ref)}` : title(item_id,place_ref);
    const details = [date,subject,observationFields[field] ?? field,reason && (reasons[reason] ?? reason),
      departure_at && `출발 기준 ${departure_at}`].filter(Boolean).join(' · ');
    return `<li>${e(details)}</li>`;
  }).join('');
  return `${unplaced ? `<h4>미배치 방문</h4><ul>${unplaced}</ul>` : ''}
    ${missing ? `<h4>관측 미확인</h4><ul>${missing}</ul>` : ''}`;
}
