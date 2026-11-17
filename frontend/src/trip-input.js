export function readAnchor(data,key) {
  const label = data[key + '_label'];
  if (!label && !data[key + '_latitude'] && !data[key + '_longitude']) return null;
  if (!label || data[key + '_latitude'] === '' || data[key + '_latitude'] == null || data[key + '_longitude'] === '' || data[key + '_longitude'] == null) throw new Error('거점 명칭·위도·경도를 모두 입력하세요.');
  return {label,latitude:Number(data[key + '_latitude']),longitude:Number(data[key + '_longitude'])};
}
