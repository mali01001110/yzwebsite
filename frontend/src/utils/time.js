/** Zero-pads a time part to the two-digit readout every HUD display expects. */
export function padTimePart(value) {
  return String(value).padStart(2, '0');
}

/** Renders a Date as a 24-hour `HH:MM:SS` terminal clock. */
export function formatClock(date) {
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map(padTimePart).join(':');
}
