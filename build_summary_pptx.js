const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.title = "IntellIntents — Resumen";
pres.author = "IntellIntents";

// Palette: Midnight Executive
const NAVY = "1E2761";
const ICE = "CADCFC";
const WHITE = "FFFFFF";
const ACCENT = "F96167"; // coral accent for emphasis
const GREY = "5A6072";
const LIGHT = "F4F6FB";

// ---------- Slide 1 — Portada / Resumen ----------
const s1 = pres.addSlide();
s1.background = { color: NAVY };

// Decorative accent bar (left)
s1.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 0.25, h: 7.5, fill: { color: ACCENT }, line: { color: ACCENT }
});

s1.addText("IntellIntents", {
  x: 0.7, y: 0.6, w: 12, h: 0.8, fontSize: 14, fontFace: "Calibri",
  color: ICE, bold: true, charSpacing: 8, margin: 0
});

s1.addText("Clasificación de Intenciones Conversacionales", {
  x: 0.7, y: 1.3, w: 12, h: 1.1, fontSize: 44, fontFace: "Georgia",
  color: WHITE, bold: true, margin: 0
});

s1.addText("Plataforma LLM para asesor de inversión (ES) — taxonomía FII v1", {
  x: 0.7, y: 2.5, w: 12, h: 0.5, fontSize: 18, fontFace: "Calibri",
  color: ICE, italic: true, margin: 0
});

// 4 stat callouts
const stats = [
  { num: "14", lbl: "Categorías" },
  { num: "87", lbl: "Sub-intenciones" },
  { num: "146 K", lbl: "Conversaciones" },
  { num: "514 K", lbl: "Turnos" },
];
const baseX = 0.7, baseY = 4.1, cardW = 2.9, cardH = 2.3, gap = 0.2;
stats.forEach((s, i) => {
  const x = baseX + i * (cardW + gap);
  s1.addShape(pres.shapes.RECTANGLE, {
    x, y: baseY, w: cardW, h: cardH,
    fill: { color: WHITE, transparency: 92 },
    line: { color: ICE, width: 0.5 },
  });
  s1.addText(s.num, {
    x, y: baseY + 0.35, w: cardW, h: 1.3, fontSize: 60, fontFace: "Georgia",
    color: WHITE, bold: true, align: "center", valign: "middle", margin: 0
  });
  s1.addText(s.lbl, {
    x, y: baseY + 1.55, w: cardW, h: 0.5, fontSize: 16, fontFace: "Calibri",
    color: ICE, align: "center", charSpacing: 4, margin: 0
  });
});

s1.addText("Stack: FastAPI · SQLite · React/Vite · LLMs (OpenAI / Anthropic)", {
  x: 0.7, y: 6.8, w: 12, h: 0.4, fontSize: 12, fontFace: "Calibri",
  color: ICE, italic: true, margin: 0
});

// ---------- Slide 2 — Taxonomía & Clasificación en cascada ----------
const s2 = pres.addSlide();
s2.background = { color: LIGHT };

// Top accent
s2.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 13.3, h: 0.18, fill: { color: NAVY }, line: { color: NAVY }
});

s2.addText("Taxonomía & Clasificación", {
  x: 0.6, y: 0.4, w: 12, h: 0.7, fontSize: 32, fontFace: "Georgia",
  color: NAVY, bold: true, margin: 0
});
s2.addText("Pipeline en cascada de 2 etapas — FII v1", {
  x: 0.6, y: 1.05, w: 12, h: 0.4, fontSize: 14, fontFace: "Calibri",
  color: GREY, italic: true, margin: 0
});

// LEFT: Cascading flow
const flowX = 0.6, flowY = 1.7, flowW = 5.6;

s2.addText("Pipeline", {
  x: flowX, y: flowY, w: flowW, h: 0.4, fontSize: 16, fontFace: "Calibri",
  color: NAVY, bold: true, charSpacing: 4, margin: 0
});

// Stage 1 box
s2.addShape(pres.shapes.RECTANGLE, {
  x: flowX, y: flowY + 0.5, w: flowW, h: 1.3,
  fill: { color: WHITE }, line: { color: ICE, width: 1 },
});
s2.addShape(pres.shapes.RECTANGLE, {
  x: flowX, y: flowY + 0.5, w: 0.1, h: 1.3, fill: { color: NAVY }, line: { color: NAVY }
});
s2.addText("Etapa 1 — Router de Categoría", {
  x: flowX + 0.25, y: flowY + 0.6, w: flowW - 0.4, h: 0.4,
  fontSize: 15, bold: true, color: NAVY, fontFace: "Calibri", margin: 0
});
s2.addText([
  { text: "Entrada: msg del usuario → 1 de 14 categorías", options: { breakLine: true } },
  { text: "Salida: categoría · confianza · razonamiento", options: { breakLine: true } },
  { text: "Umbral por def. 0.60 → si < umbral → UNKNOWN" },
], {
  x: flowX + 0.25, y: flowY + 0.95, w: flowW - 0.4, h: 0.85,
  fontSize: 11, color: GREY, fontFace: "Calibri", margin: 0
});

// Arrow
s2.addShape(pres.shapes.LINE, {
  x: flowX + flowW / 2, y: flowY + 1.85, w: 0, h: 0.3,
  line: { color: NAVY, width: 2, endArrowType: "triangle" }
});

// Stage 2 box
s2.addShape(pres.shapes.RECTANGLE, {
  x: flowX, y: flowY + 2.2, w: flowW, h: 1.3,
  fill: { color: WHITE }, line: { color: ICE, width: 1 },
});
s2.addShape(pres.shapes.RECTANGLE, {
  x: flowX, y: flowY + 2.2, w: 0.1, h: 1.3, fill: { color: ACCENT }, line: { color: ACCENT }
});
s2.addText("Etapa 2 — Sub-Intención", {
  x: flowX + 0.25, y: flowY + 2.3, w: flowW - 0.4, h: 0.4,
  fontSize: 15, bold: true, color: NAVY, fontFace: "Calibri", margin: 0
});
s2.addText([
  { text: "Entrada: msg + categoría → 1 de 6–8 hojas", options: { breakLine: true } },
  { text: "Salida: intención · confianza · razonamiento", options: { breakLine: true } },
  { text: "Umbral 0.65 → si < umbral → fallback al padre" },
], {
  x: flowX + 0.25, y: flowY + 2.65, w: flowW - 0.4, h: 0.85,
  fontSize: 11, color: GREY, fontFace: "Calibri", margin: 0
});

// Final confidence
s2.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: flowX, y: flowY + 3.7, w: flowW, h: 0.6,
  fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.08
});
s2.addText("Confianza final = conf₁ × conf₂", {
  x: flowX, y: flowY + 3.7, w: flowW, h: 0.6,
  fontSize: 14, bold: true, color: WHITE, align: "center", valign: "middle",
  fontFace: "Consolas", margin: 0
});

// Variantes
s2.addText("Variantes: cascading · cascading_context (Modo A estático / Modo B encadenado)", {
  x: flowX, y: flowY + 4.45, w: flowW, h: 0.4,
  fontSize: 10, italic: true, color: GREY, fontFace: "Calibri", margin: 0
});

// RIGHT: Taxonomy categories
const tx = 6.6, ty = 1.7, tw = 6.1;
s2.addText("14 Categorías Top-Level", {
  x: tx, y: ty, w: tw, h: 0.4, fontSize: 16, fontFace: "Calibri",
  color: NAVY, bold: true, charSpacing: 4, margin: 0
});

const cats = [
  ["ONBOARDING_KYC", "6"],
  ["INVESTOR_PROFILING", "8"],
  ["PRODUCT_DISCOVERY", "8"],
  ["RECOMMENDATION_ADVISORY", "8"],
  ["EXECUTION_TRANSACTIONS", "7"],
  ["PORTFOLIO_MONITORING", "7"],
  ["FINANCIAL_EDUCATION", "7"],
  ["ACCOUNT_SERVICE_MGMT", "8"],
  ["REGULATORY_COMPLIANCE", "7"],
  ["GREETING", "3"],
  ["SMALL_TALK", "5"],
  ["OUT_OF_SCOPE", "5"],
  ["HARMFUL_UNETHICAL", "4"],
  ["UNKNOWN", "1"],
];

const tableData = [
  [
    { text: "Categoría", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontFace: "Calibri", fontSize: 11, align: "left", valign: "middle" } },
    { text: "Sub", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontFace: "Calibri", fontSize: 11, align: "center", valign: "middle" } },
  ],
  ...cats.map((c, i) => [
    { text: c[0], options: { fontFace: "Calibri", fontSize: 10, color: NAVY, fill: { color: i % 2 === 0 ? WHITE : LIGHT }, valign: "middle" } },
    { text: c[1], options: { fontFace: "Calibri", fontSize: 10, color: ACCENT, bold: true, align: "center", fill: { color: i % 2 === 0 ? WHITE : LIGHT }, valign: "middle" } },
  ]),
];

s2.addTable(tableData, {
  x: tx, y: ty + 0.45, w: tw, colW: [tw - 1, 1],
  rowH: 0.27,
  border: { type: "none" },
});

s2.addText("Total: 87 hojas + 14 padres = 101 etiquetas", {
  x: tx, y: ty + 4.9, w: tw, h: 0.3, fontSize: 11, italic: true,
  color: GREY, fontFace: "Calibri", margin: 0
});

// ---------- Slide 3 — Dataset & Hallazgos ----------
const s3 = pres.addSlide();
s3.background = { color: WHITE };

// Side accent bar (right)
s3.addShape(pres.shapes.RECTANGLE, {
  x: 13.05, y: 0, w: 0.25, h: 7.5, fill: { color: NAVY }, line: { color: NAVY }
});

s3.addText("Dataset & Hallazgos Clave", {
  x: 0.6, y: 0.4, w: 12, h: 0.7, fontSize: 32, fontFace: "Georgia",
  color: NAVY, bold: true, margin: 0
});
s3.addText("Corpus GPTAdvisor — 146 127 conv · 514 814 turnos · ES", {
  x: 0.6, y: 1.05, w: 12, h: 0.4, fontSize: 14, fontFace: "Calibri",
  color: GREY, italic: true, margin: 0
});

// LEFT: Bar chart of top categories
const chartCats = [
  { lbl: "ACCOUNT_SVC_MGMT", val: 33.13 },
  { lbl: "PRODUCT_DISCOVERY", val: 25.38 },
  { lbl: "EXECUTION_TX", val: 14.98 },
  { lbl: "ONBOARDING_KYC", val: 7.26 },
  { lbl: "PORTFOLIO_MONIT.", val: 6.69 },
  { lbl: "FINANCIAL_EDU", val: 4.46 },
  { lbl: "OUT_OF_SCOPE", val: 2.11 },
  { lbl: "RECOMMEND_ADV", val: 1.89 },
  { lbl: "GREETING", val: 1.38 },
  { lbl: "UNKNOWN", val: 1.0 },
  { lbl: "REG_COMPLIANCE", val: 0.89 },
  { lbl: "INVESTOR_PROF", val: 0.10 },
];

s3.addText("Distribución por categoría (% turnos)", {
  x: 0.6, y: 1.6, w: 6.3, h: 0.4, fontSize: 14, bold: true,
  color: NAVY, fontFace: "Calibri", margin: 0
});

s3.addChart(pres.charts.BAR, [{
  name: "% turnos",
  labels: chartCats.map(c => c.lbl),
  values: chartCats.map(c => c.val),
}], {
  x: 0.6, y: 2.0, w: 6.3, h: 5.0, barDir: "bar",
  chartColors: [NAVY],
  chartArea: { fill: { color: WHITE }, roundedCorners: false },
  catAxisLabelColor: GREY, catAxisLabelFontSize: 9, catAxisLabelFontFace: "Calibri",
  valAxisLabelColor: GREY, valAxisLabelFontSize: 9, valAxisLabelFontFace: "Calibri",
  valGridLine: { color: "E2E8F0", size: 0.5 },
  catGridLine: { style: "none" },
  showValue: true,
  dataLabelPosition: "outEnd",
  dataLabelColor: NAVY,
  dataLabelFontSize: 9,
  dataLabelFormatCode: "0.00\"%\"",
  showLegend: false,
});

// RIGHT: Key findings cards
const fx = 7.3, fy = 1.6, fw = 5.5;
s3.addText("Hallazgos", {
  x: fx, y: fy, w: fw, h: 0.4, fontSize: 14, bold: true,
  color: NAVY, fontFace: "Calibri", margin: 0
});

const findings = [
  {
    k: "Bot operativo, no asesor",
    v: "ADVISORY + PROFILING < 2 % del corpus",
    color: NAVY,
  },
  {
    k: "Conversaciones cortas",
    v: "Mediana = 2 turnos · 85 % con ≤ 2 intenciones",
    color: NAVY,
  },
  {
    k: "Brecha de idoneidad (MiFID II)",
    v: "81.5 % de conv. con intenciones de alto riesgo SIN señal de perfilado",
    color: ACCENT,
  },
  {
    k: "Fiabilidad crítica",
    v: "buy_investment 67 % · transfer_funds 47 % · ask_about_fees 64 % filas con conf < 0.7",
    color: ACCENT,
  },
  {
    k: "Escalado a humano",
    v: "4.80 % del corpus · 29 % de file_complaint termina en escalado",
    color: NAVY,
  },
];

const fcardH = 1.0, fcardGap = 0.08;
findings.forEach((f, i) => {
  const y = fy + 0.5 + i * (fcardH + fcardGap);
  s3.addShape(pres.shapes.RECTANGLE, {
    x: fx, y, w: fw, h: fcardH,
    fill: { color: LIGHT }, line: { color: ICE, width: 0.5 },
  });
  s3.addShape(pres.shapes.RECTANGLE, {
    x: fx, y, w: 0.08, h: fcardH, fill: { color: f.color }, line: { color: f.color }
  });
  s3.addText(f.k, {
    x: fx + 0.22, y: y + 0.08, w: fw - 0.3, h: 0.32,
    fontSize: 12, bold: true, color: NAVY, fontFace: "Calibri", margin: 0
  });
  s3.addText(f.v, {
    x: fx + 0.22, y: y + 0.4, w: fw - 0.3, h: 0.55,
    fontSize: 11, color: GREY, fontFace: "Calibri", margin: 0
  });
});

s3.addText("Fuente: docs/intent-distribution-statistical-analysis.md · docs/compliance-risk-analysis.md", {
  x: 0.6, y: 7.05, w: 12, h: 0.3, fontSize: 9, italic: true,
  color: GREY, fontFace: "Calibri", margin: 0
});

pres.writeFile({ fileName: "/Users/reynier/Work/PythonProjects/intellintents/IntellIntents_Resumen.pptx" })
  .then(f => console.log("OK:", f));
