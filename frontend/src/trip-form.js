import {readTripConfig} from './trip-input.js';
import {appendCost,readFixedCosts} from './fixed-costs.js';

export function readTripForm(form) {
  const data = Object.fromEntries(new FormData(form));
  return {title:data.title,...readTripConfig(data, readFixedCosts())};
}

export function restoreTripForm(snapshot) {
  const form = document.getElementById('trip');
  form.elements.title.value = snapshot.title;
  for (const [key,value] of Object.entries(snapshot.config)) {
    if (form.elements[key]) form.elements[key].value = value;
  }
  const {title,...baseline} = readTripForm(form);
  return baseline;
}
