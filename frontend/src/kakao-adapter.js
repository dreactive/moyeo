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
export function drawKakao(maps,element,points,lines = []) {
  if (!points.length) { element.textContent = '표시할 좌표가 없습니다.'; return; }
  element.innerHTML = '';
  element.classList.add('sdk');
  const latLng = point => new maps.LatLng(point.latitude,point.longitude);
  const map = new maps.Map(element,{center:latLng(points[0]),level:6});
  const bounds = new maps.LatLngBounds();
  points.forEach(point => {
    const position = latLng(point);
    new maps.Marker({map,position,title:point.name ?? point.label});
    bounds.extend(position);
  });
  lines.forEach((line,index) => new maps.Polyline({map,path:line.map(latLng),strokeWeight:4,strokeColor:['#24745b','#b97720'][index % 2]}));
  map.setBounds(bounds);
  return {map,latLng};
}
