import {escapeHtml as e} from './ui.js';
import {getSnapshot} from './state.js';
const categoryText = {lodging:'숙박',intercity_transport:'장거리 교통',meal:'식사',admission:'입장·체험',car:'차량(유류·주차·통행료)',other:'기타'};
const scopeText = {shared:'함께 나눔',per_person:'1인당 각각'};
const ownerOptions = (owner,members) => {
  const known = members.some(member => member.user_id === owner);
  return `<option value="">전체 참가자</option>${members.map(member => `<option value="${e(member.user_id)}" ${member.user_id === owner ? 'selected' : ''}>${e(member.name)}</option>`).join('')}${owner && !known ? `<option value="${e(owner)}" selected>${e(owner)}</option>` : ''}`;
};
export function appendCost(line = {id:crypto.randomUUID(),category:'lodging',scope:'shared',description:'',unit_price_krw:null,quantity:1,paid:false,owner_id:null},members) {
  if (!Array.isArray(members)) members = getSnapshot()?.members ?? [];
  document.getElementById('fixed-costs').insertAdjacentHTML('beforeend',`<div class="cost-row" data-cost-id="${e(line.id)}">
  <label>종류<select name="cost_category">${['lodging','intercity_transport','meal','admission','car','other'].map(value => `<option value="${value}" ${line.category === value ? 'selected' : ''}>${categoryText[value]}</option>`).join('')}</select></label>
  <label>분담<select name="cost_scope">${['shared','per_person'].map(value => `<option value="${value}" ${line.scope === value ? 'selected' : ''}>${scopeText[value]}</option>`).join('')}</select></label>
  <label>대상<select name="cost_owner">${ownerOptions(line.owner_id,members)}</select></label>
  <label>설명<input name="cost_description" value="${e(line.description)}" required></label>
  <label>단가 (원)<input name="cost_price" type="number" min="0" value="${e(line.unit_price_krw)}"></label>
  <label>수량<input name="cost_quantity" type="number" min="0.01" step="any" value="${e(line.quantity)}" required></label>
  <label>지출<select name="cost_paid"><option value="false">예정</option><option value="true" ${line.paid ? 'selected' : ''}>기지출</option></select></label><button type="button" data-remove-cost>삭제</button></div>`);
}
export function refreshCostOwners(members = []) {
  const basis = JSON.stringify(members);
  for (const select of document.querySelectorAll('[name=cost_owner]')) {
    if (select.dataset.ownerMembers === basis) continue;
    const owner = select.value;
    select.innerHTML = ownerOptions(owner,members);
    select.value = owner;
    select.dataset.ownerMembers = basis;
  }
}
export function readFixedCosts() {
  return [...document.querySelectorAll('[data-cost-id]')].map(row => {
    const value = name => row.querySelector('[name=cost_' + name + ']').value;
    return {id:row.dataset.costId,category:value('category'),scope:value('scope'),owner_id:value('owner') || null,description:value('description'),unit_price_krw:value('price') === '' ? null : Number(value('price')),quantity:Number(value('quantity')),paid:value('paid') === 'true',subtotal_krw:null,evidence_id:null,assumption:null};
  });
}
