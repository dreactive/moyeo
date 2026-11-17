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
