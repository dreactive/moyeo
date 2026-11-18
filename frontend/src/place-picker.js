import {escapeHtml as e} from './ui.js';
import {loadKakao} from './kakao-adapter.js';

export const DEFAULT_CENTER = {latitude:34.7604,longitude:127.6622};
export function anchorFromKakao(item) {
  return {
    label:item.place_name || item.address_name,
    address:item.road_address_name || item.address_name || '',
    latitude:Number(Number(item.y).toFixed(6)),
    longitude:Number(Number(item.x).toFixed(6)),
    source_ref:item.id ? 'kakao:place:' + item.id : null,
  };
}
export const coordinateText = anchor => anchor && Number.isFinite(anchor.latitude) && Number.isFinite(anchor.longitude)
  ? `${anchor.latitude.toFixed(5)}, ${anchor.longitude.toFixed(5)}` : '';

let mapsPromise = null;
const loadServices = appKey => {
  if (!appKey) return Promise.resolve(null);
  mapsPromise ??= loadKakao(appKey).then(maps => maps?.services ? maps : null).catch(() => null);
  return mapsPromise;
};
const field = (root,name) => root.querySelector(`[name="${name}"],[name$="_${name}"]`);
function readInputs(root) {
  const lat = field(root,'latitude')?.value, lon = field(root,'longitude')?.value;
  return {label:field(root,'label')?.value ?? '',latitude:lat === '' ? NaN : Number(lat),longitude:lon === '' ? NaN : Number(lon)};
}
function writeInputs(root,anchor) {
  const set = (name,value) => { const input = field(root,name); if (input) { input.value = value ?? ''; input.dispatchEvent(new Event('input',{bubbles:true})); } };
  set('label',anchor.label); set('latitude',anchor.latitude); set('longitude',anchor.longitude); set('source_ref',anchor.source_ref ?? '');
}
export function clearAnchor(root) {
  writeInputs(root,{label:'',latitude:'',longitude:'',source_ref:''});
  const query = root.querySelector('input[type=search]');
  if (query) query.value = '';
  for (const selector of ['.anchor-results','.anchor-map']) {
    const panel = root.querySelector(selector);
    if (panel) panel.hidden = true;
  }
  refreshAnchorSummaries(root.parentElement ?? document);
}
function bindAnchorControls(root) {
  if (root.dataset.anchorControls) return;
  root.dataset.anchorControls = 'true';
  const clear = root.querySelector('[data-clear-anchor]');
  if (clear) clear.onclick = () => clearAnchor(root);
  root.addEventListener('input',event => {
    if (event.isTrusted && /(latitude|longitude)$/.test(event.target.name ?? '')) {
      const ref = field(root,'source_ref');
      if (ref) ref.value = '';
    }
    refreshAnchorSummaries(root.parentElement ?? document);
  });
}
export function refreshAnchorSummaries(scope = document) {
  scope.querySelectorAll('[data-anchor-picker].has-picker').forEach(root => {
    const anchor = readInputs(root);
    const summary = root.querySelector('.anchor-picked');
    summary.innerHTML = anchor.label && coordinateText(anchor) ? `<strong>${e(anchor.label)}</strong>` : '<span class="muted">아직 고르지 않았어요</span>';
  });
}
function search(maps,query) {
  return new Promise(resolve => {
    new maps.services.Places().keywordSearch(query,(data,status) => {
      if (status === maps.services.Status.OK && data.length) return resolve(data.slice(0,6));
      new maps.services.Geocoder().addressSearch(query,(rows,code) => resolve(code === maps.services.Status.OK ? rows.slice(0,6) : []));
    },{size:6});
  });
}
function reverse(maps,latitude,longitude) {
  return new Promise(resolve => new maps.services.Geocoder().coord2Address(longitude,latitude,(rows,status) => {
    const row = status === maps.services.Status.OK ? rows[0] : null;
    resolve(row ? (row.road_address?.building_name || row.road_address?.address_name || row.address?.address_name) : null);
  }));
}
function enhance(root,maps) {
  root.classList.add('has-picker');
  const labelInput = field(root,'label');
  if (labelInput) labelInput.placeholder = '표시 이름 (검색하면 자동 입력)';
  const ui = document.createElement('div');
  ui.className = 'anchor-picker';
  ui.innerHTML = `<p class="anchor-picked"></p>
  <div class="anchor-search"><input type="search" placeholder="장소·주소 검색 (예: 여수엑스포역)" aria-label="장소 검색" enterkeyhint="search"><button type="button" data-anchor-search>검색</button><button type="button" class="ghost" data-anchor-map>지도에서 고르기</button></div>
  <ul class="anchor-results" hidden></ul><div class="anchor-map" hidden></div>`;
  root.append(ui);
  if (labelInput) ui.querySelector('.anchor-picked').after(labelInput);
  const query = ui.querySelector('input[type=search]'), results = ui.querySelector('.anchor-results'), mapBox = ui.querySelector('.anchor-map');
  let found = [], map = null, marker = null;
  const choose = anchor => {
    writeInputs(root,anchor); refreshAnchorSummaries(root.parentElement ?? document);
    results.hidden = true; results.innerHTML = ''; query.value = '';
    if (map) { const at = new maps.LatLng(anchor.latitude,anchor.longitude); map.setCenter(at); marker.setPosition(at); }
  };
  const runSearch = async () => {
    const text = query.value.trim();
    if (!text) return query.focus();
    results.hidden = false; results.innerHTML = '<li class="muted">찾는 중…</li>';
    found = (await search(maps,text)).map(anchorFromKakao);
    results.innerHTML = found.length ? found.map((anchor,index) => `<li><button type="button" data-anchor-pick="${index}"><strong>${e(anchor.label)}</strong><span>${e(anchor.address)}</span></button></li>`).join('') : '<li class="muted">검색 결과가 없어요. 다른 이름이나 주소로 찾아보세요.</li>';
  };
  ui.querySelector('[data-anchor-search]').onclick = runSearch;
  query.onkeydown = event => { if (event.key === 'Enter') { event.preventDefault(); runSearch(); } };
  results.onclick = event => { const pick = event.target.closest('[data-anchor-pick]'); if (pick) choose(found[Number(pick.dataset.anchorPick)]); };
  ui.querySelector('[data-anchor-map]').onclick = event => {
    mapBox.hidden = !mapBox.hidden;
    event.currentTarget.textContent = mapBox.hidden ? '지도에서 고르기' : '지도 닫기';
    if (mapBox.hidden) return;
    const current = readInputs(root);
    const start = Number.isFinite(current.latitude) && Number.isFinite(current.longitude) ? current : DEFAULT_CENTER;
    const center = new maps.LatLng(start.latitude,start.longitude);
    if (!map) {
      map = new maps.Map(mapBox,{center,level:5});
      marker = new maps.Marker({map,position:center});
      maps.event.addListener(map,'click',async mouse => {
        const latitude = Number(mouse.latLng.getLat().toFixed(6)), longitude = Number(mouse.latLng.getLng().toFixed(6));
        marker.setPosition(mouse.latLng);
        const label = await reverse(maps,latitude,longitude);
        choose({label:label || `지도에서 고른 위치`,latitude,longitude,source_ref:null});
      });
    } else { map.relayout(); map.setCenter(center); marker.setPosition(center); }
  };
}
export async function enhanceAnchorPickers(appKey,scope = document) {
  const roots = [...scope.querySelectorAll('[data-anchor-picker]:not(.has-picker)')];
  if (!roots.length) return false;
  roots.forEach(bindAnchorControls);
  const maps = await loadServices(appKey);
  for (const root of roots) {
    const manual = root.querySelector('[data-anchor-manual]');
    const hint = root.querySelector('[data-anchor-fallback]');
    if (manual) manual.open = !maps;
    if (hint) hint.hidden = !!maps;
  }
  if (!maps) return false;
  roots.filter(root => root.isConnected && !root.classList.contains('has-picker')).forEach(root => enhance(root,maps));
  refreshAnchorSummaries(scope);
  return true;
}
