import {readTripConfig} from './trip-input.js';
import {appendCost,readFixedCosts} from './fixed-costs.js';

export function readTripForm(form) {
  const data = Object.fromEntries(new FormData(form));
  return {title:data.title,...readTripConfig(data, readFixedCosts())};
}
