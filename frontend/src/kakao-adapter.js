const layersByHost = new WeakMap();

export async function loadKakao(appKey) {
  if (!appKey) return null;
  if (!globalThis.kakao?.maps) await new Promise((resolve,reject) => {
    const script = document.createElement('script');
    script.src = 'https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=' + encodeURIComponent(appKey);
    script.onload = resolve;
    script.onerror = () => reject(new Error('지도 SDK 로딩 실패 · 키/허용 도메인을 확인하세요.'));
    document.head.append(script);
  });
  await new Promise(resolve => kakao.maps.load(resolve));
  return kakao.maps;
}
export function clearKakao(element) {
  for (const layer of layersByHost.get(element) ?? []) layer.setMap?.(null);
  layersByHost.delete(element);
  element.classList?.remove?.('sdk');
  element.innerHTML = '';
}
export function drawKakao(maps,element,points,lines = []) {
  clearKakao(element);
  if (!points.length) { element.textContent = '표시할 좌표가 없습니다.'; return; }
  element.classList.add('sdk');
  const viewport = element.ownerDocument?.createElement('div') ?? element;
  if (viewport !== element) {
    viewport.style.cssText = 'width:100%;height:100%';
    element.append(viewport);
  }
  const latLng = point => new maps.LatLng(point.latitude,point.longitude);
  const map = new maps.Map(viewport,{center:latLng(points[0]),level:6});
  const layers = [];
  layersByHost.set(element,layers);
  const bounds = new maps.LatLngBounds();
  points.forEach(point => {
    const position = latLng(point);
    const name = point.name ?? point.label;
    const agreement = point.agreement;
    const status = agreement ? [agreement.label,agreement.counts,agreement.conflict ? '! 충돌' : ''].filter(Boolean).join(' · ') : '';
    const title = `${point.visitNumber ? point.visitNumber + '. ' : ''}${name}${status ? ' · ' + status : ''}`;
    if ((point.visitNumber || point.mention) && maps.CustomOverlay && element.ownerDocument) {
      const content = element.ownerDocument.createElement('span');
      const label = point.mention ? (point.unplaced ? '미배치' : name) : String(point.visitNumber);
      content.textContent = agreement ? `${label} · ${agreement.label}${agreement.conflict ? ' !' : ''}` : label;
      content.title = title;
      content.className = `map-visit-pin${agreement ? ' ' + agreement.state : ''}`;
      layers.push(new maps.CustomOverlay({map,position,content}));
    } else {
      layers.push(new maps.Marker({map,position,title}));
    }
    bounds.extend(position);
  });
  lines.forEach((line,index) => {
    layers.push(new maps.Polyline({map,path:line.map(latLng),strokeWeight:4,strokeColor:['#4a5592','#7666b7'][index % 2]}));
  });
  map.setBounds(bounds);
  return {map,latLng};
}
