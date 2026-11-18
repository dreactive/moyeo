import {readAnchor,readTripConfig} from './trip-input.js';
import {appendCost,readFixedCosts} from './fixed-costs.js';

export function readTripForm(form) {
  const data = Object.fromEntries(new FormData(form));
  return {title:data.title,...readTripConfig(data, readFixedCosts()),origin:readAnchor(data,'origin'),destination:readAnchor(data,'destination')};
}

export function restoreTripForm(snapshot) {
  const form = document.getElementById('trip');
  form.elements.title.value = snapshot.title;
  for (const [key,value] of Object.entries(snapshot.config)) {
    if (form.elements[key]) form.elements[key].value = value;
  }
  for (const anchor of ['origin','destination','lodging']) {
    for (const field of ['label','latitude','longitude']) {
      const input = form.elements[anchor + '_' + field];
      if (input) input.value = snapshot.config[anchor]?.[field] ?? '';
    }
  }
  if (snapshot.config.fixed_costs) {
    document.getElementById('fixed-costs').innerHTML = '';
    snapshot.config.fixed_costs.forEach(line => appendCost(line,snapshot.members));
  }
  const {title,...baseline} = readTripForm(form);
  return baseline;
}

export function bindFixedCostControls() {
  document.getElementById('add-cost').onclick = () => appendCost();
  document.getElementById('fixed-costs').onclick = event => {
    event.target.closest('[data-remove-cost]')?.closest('[data-cost-id]').remove();
  };
}
