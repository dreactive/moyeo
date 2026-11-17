import {escapeHtml as e} from './ui.js';
export function appendCost(line = {id:crypto.randomUUID(),category:'lodging',scope:'shared',description:'',unit_price_krw:null,quantity:1,paid:false,owner_id:null}) {
  document.getElementById('fixed-costs').insertAdjacentHTML('beforeend',`<div class="cost-row" data-cost-id="${e(line.id)}">
  <label>종류<select name="cost_category">${['lodging','intercity_transport','meal','admission','car','other'].map(value => `<option ${line.category === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
  <label>분담<select name="cost_scope">${['shared','per_person'].map(value => `<option ${line.scope === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
  <label>대상 ID (공란=전체)<input name="cost_owner" value="${e(line.owner_id)}"></label>
  <label>설명<input name="cost_description" value="${e(line.description)}" required></label>
  <label>단가 (원)<input name="cost_price" type="number" min="0" value="${e(line.unit_price_krw)}"></label>
  <label>수량<input name="cost_quantity" type="number" min="0.01" step="any" value="${e(line.quantity)}" required></label>
  <label>지출<select name="cost_paid"><option value="false">예정</option><option value="true" ${line.paid ? 'selected' : ''}>기지출</option></select></label><button type="button" data-remove-cost>삭제</button></div>`);
}
export function readFixedCosts() {
  return [...document.querySelectorAll('[data-cost-id]')].map(row => {
    const value = name => row.querySelector('[name=cost_' + name + ']').value;
    return {id:row.dataset.costId,category:value('category'),scope:value('scope'),owner_id:value('owner') || null,description:value('description'),unit_price_krw:value('price') === '' ? null : Number(value('price')),quantity:Number(value('quantity')),paid:value('paid') === 'true',subtotal_krw:null,evidence_id:null,assumption:null};
  });
}
