const PALETTE = [
  '#22d3ee', // cyan-400
  '#a78bfa', // violet-400
  '#34d399', // emerald-400
  '#f472b6', // pink-400
  '#fb923c', // orange-400
  '#facc15', // yellow-400
  '#60a5fa', // blue-400
  '#f87171', // red-400
  '#4ade80', // green-400
  '#c084fc', // purple-400
  '#2dd4bf', // teal-400
  '#fbbf24', // amber-400
  '#818cf8', // indigo-400
  '#fb7185', // rose-400
  '#38bdf8', // sky-400
  '#a3e635', // lime-400
  '#e879f9', // fuchsia-400
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash);
}

export function getIntentColor(intentName) {
  if (!intentName) return PALETTE[0];
  const index = hashString(intentName) % PALETTE.length;
  return PALETTE[index];
}

export function getIntentColorWithAlpha(intentName, alpha = 0.3) {
  const hex = getIntentColor(intentName);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export { PALETTE };
