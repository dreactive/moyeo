import {displayPlan,planAgreement} from './plan.js';
import {escapeHtml as e,html} from './ui.js';
import {agreementLegend,agreementMarkup,planItemAgreements} from './agreement.js';
import {currentAgentResults,itineraryGaps,resultBasis} from './agent-results.js';
import {routeLegMarkup,dailyAnchors} from './map.js';

const clock = new Intl.DateTimeFormat('en-GB', {
  timeZone:'Asia/Seoul', hour:'2-digit', minute:'2-digit'
});

export function renderRoutePanel(snapshot, date) {
  const plan = displayPlan(snapshot);
  const days = plan?.days ?? [];
  const selected = days.find(day => day.date === date) ?? days[0];
  html('route-days', days.map((day,index) => `<button type="button" aria-pressed="${day === selected}" data-day="${e(day.date)}" title="${e(day.date)}">${index + 1}일차</button>`).join(''));
  html('route-legend',selected?.visits.length ? agreementLegend : '');
  const context = plan ? `<p class="muted">여행안 v${e(plan.plan_revision)} · ${planAgreement(snapshot,plan).status}</p>` : '';
  const anchors = selected && plan.missing_observations == null ? dailyAnchors(days,selected) : null;
  const agreements = planItemAgreements(snapshot,plan);
  const visits = selected ? `${visitList(selected.visits,plan.item_snapshots,agreements)}
    ${routeLegs(selected,plan.item_snapshots,snapshot.config,anchors)}` : '';
  const gaps = plan ? itineraryGaps(plan,plan.item_snapshots,snapshot.config,agreements) : '';
  html('route-summary', `${context}${visits}${gaps}${partialItinerary(snapshot)}`);
}

function visitList(visits,items,agreements) {
  if (!visits.length) return '<p class="muted">이 날에 예정된 방문이 없어요.</p>';
  const titles = new Map(items.map(item => [item.id,item.title]));
  return `<ol>${visits.map(visit => `<li>
    <button type="button" data-place="${e(visit.place_ref)}">${e(titles.get(visit.item_id) ?? visit.place_ref)}</button>
    <small>${clock.format(new Date(visit.start_at))}–${clock.format(new Date(visit.end_at))} · 체류 ${e(visit.stay_minutes)}분</small>
    ${visit.assumptions?.length ? `<small class="muted">가정 ${e(visit.assumptions.join(' · '))}</small>` : ''}
    ${agreements ? agreementMarkup(agreements.get(visit.item_id)) : ''}
  </li>`).join('')}</ol>`;
}

function routeLegs(day,items,config,anchors) {
  const titles = new Map(items.filter(item => item.place_ref).map(item => [item.place_ref,item.title]));
  for (const visit of day.visits) titles.set(visit.place_ref,items.find(item => item.id === visit.item_id)?.title ?? visit.place_ref);
  for (const [key,label] of Object.entries({origin:'출발지',lodging:'숙소',destination:'귀가지'})) {
    titles.set(`anchor:${key}`,config[key]?.label ?? label);
  }
  const label = ref => e(titles.get(ref) ?? ref);
  const legs = day.route_legs ?? [];
  const refs = anchors ? [`anchor:${anchors[0]}`,...day.visits.map(visit => visit.place_ref),`anchor:${anchors.at(-1)}`] : [];
  const missing = refs.slice(1).flatMap((to,index) => {
    const from = refs[index];
    return from === to || legs.some(leg => leg.from_ref === from && leg.to_ref === to)
      ? [] : [`<li>${label(from)} → ${label(to)} · 경로 미조회</li>`];
  });
  if (!legs.length && !missing.length) return '';
  return `<details class="card-details"><summary>자동차 경로 조회 · 확인 ${legs.length}구간${missing.length ? ` · 미조회 ${missing.length}구간` : ''}</summary>
    ${legs.map(leg => routeLegMarkup(leg,label)).join('')}${missing.length ? `<ul>${missing.join('')}</ul>` : ''}</details>`;
}

function partialItinerary(snapshot) {
  const results = currentAgentResults(snapshot);
  const itinerary = results?.build_itinerary;
  if (!itinerary) return '';
  const revision = results.versions?.plan_revision;
  const plan = [snapshot.current_plan,snapshot.review_plan,snapshot.confirmed_plan].find(plan => plan && plan.plan_revision === revision);
  const items = plan?.item_snapshots ?? snapshot.items;
  return `<details class="card-details" id="agent-itinerary"><summary>부분 일정</summary>${resultBasis(results)}
    ${itinerary.days.map(day => `<h4>${e(day.date)}</h4>${visitList(day.visits,items)}${routeLegs(day,items,snapshot.config)}`).join('')}
    ${itineraryGaps(itinerary,items,snapshot.config)}
    ${(itinerary.conflicts ?? []).map(conflict => `<p>! ${e(conflict.explanation)}</p>`).join('')}
    ${(itinerary.questions ?? []).map(question => `<p>${e(question.text)}</p>`).join('')}</details>`;
}
