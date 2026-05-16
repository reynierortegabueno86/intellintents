// IntellIntents — Executive Deck (5 slides) for project deliverables
// Audience: Steering / Compliance / Legal
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const {
  FaDatabase,
  FaCogs,
  FaShieldAlt,
  FaExclamationTriangle,
  FaGavel,
  FaFlagCheckered,
  FaGithub,
  FaBalanceScale,
} = require("react-icons/fa");

// ---------- Palette: Midnight Executive + Risk Coral ----------
const NAVY = "1E2761";
const NAVY_DEEP = "141A47";
const ICE = "CADCFC";
const WHITE = "FFFFFF";
const CORAL = "F96167";       // risk accent
const AMBER = "F2C14E";       // mid-risk
const TEAL = "1FAA8C";        // ok / done
const INK = "0F172A";
const SLATE = "475569";
const SLATE_LIGHT = "94A3B8";
const PAPER = "F7F8FC";

// ---------- Helpers ----------
function renderIconSvg(IconComponent, color = "#000000", size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
}
async function iconPng(IconComponent, color, size = 256) {
  const svg = renderIconSvg(IconComponent, color, size);
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
const HEADER_FONT = "Georgia";
const BODY_FONT = "Calibri";

async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
  pres.author = "Hector Garcia · Project Lead";
  pres.title = "IntellIntents — Deliverables v1";

  const SLIDE_W = 13.3;
  const SLIDE_H = 7.5;

  // Pre-render icons
  const icoDB = await iconPng(FaDatabase, "#FFFFFF", 256);
  const icoCogs = await iconPng(FaCogs, "#FFFFFF", 256);
  const icoShield = await iconPng(FaShieldAlt, "#FFFFFF", 256);
  const icoWarn = await iconPng(FaExclamationTriangle, "#" + CORAL, 256);
  const icoGavel = await iconPng(FaGavel, "#" + ICE, 256);
  const icoFlag = await iconPng(FaFlagCheckered, "#" + ICE, 256);
  const icoGit = await iconPng(FaGithub, "#" + INK, 256);
  const icoScale = await iconPng(FaBalanceScale, "#" + ICE, 256);

  // ========== SLIDE 1 — COVER ==========
  {
    const s = pres.addSlide();
    s.background = { color: NAVY_DEEP };

    // Right-side decorative panel
    s.addShape(pres.shapes.RECTANGLE, {
      x: SLIDE_W - 4.6, y: 0, w: 4.6, h: SLIDE_H,
      fill: { color: NAVY }, line: { color: NAVY, width: 0 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: SLIDE_W - 4.6, y: 0, w: 0.18, h: SLIDE_H,
      fill: { color: CORAL }, line: { color: CORAL, width: 0 },
    });

    // Project tag
    s.addText("PROYECTO  ·  ALINEAMIENTO LLM  ·  COMPLIANCE FINANCIERO", {
      x: 0.7, y: 0.7, w: 8.0, h: 0.4,
      fontFace: BODY_FONT, fontSize: 11, bold: true,
      color: CORAL, charSpacing: 4, margin: 0,
    });

    // Title
    s.addText("IntellIntents", {
      x: 0.7, y: 1.2, w: 8.5, h: 1.2,
      fontFace: HEADER_FONT, fontSize: 64, bold: true,
      color: WHITE, margin: 0,
    });
    s.addText("Plan de Entregables  ·  v1", {
      x: 0.7, y: 2.45, w: 8.5, h: 0.7,
      fontFace: HEADER_FONT, fontSize: 30, italic: true,
      color: ICE, margin: 0,
    });

    // One-line value prop
    s.addText(
      "Dataset anotado · Herramienta de análisis · Reporte de riesgo regulatorio sobre conversaciones reales de un asesor financiero LLM en España.",
      { x: 0.7, y: 3.5, w: 8.0, h: 1.4, fontFace: BODY_FONT,
        fontSize: 16, color: ICE, margin: 0 }
    );

    // Meta block bottom
    s.addText([
      { text: "Sponsor regulatorio:  ", options: { bold: true, color: ICE } },
      { text: "MiFID II · RIS · PRIIPs · SFDR · GDPR · AML/CFT", options: { color: WHITE, breakLine: true } },
      { text: "Audiencia:  ", options: { bold: true, color: ICE } },
      { text: "Steering · Compliance · Legal", options: { color: WHITE, breakLine: true } },
      { text: "Fecha:  ", options: { bold: true, color: ICE } },
      { text: "16-mayo-2026", options: { color: WHITE } },
    ], { x: 0.7, y: 5.6, w: 8.0, h: 1.5, fontFace: BODY_FONT, fontSize: 13, margin: 0 });

    // Right panel content — three deliverable chips
    const chips = [
      { icon: icoDB, label: "D1", title: "Dataset anotado", sub: "146 K conv · 514 K turns" },
      { icon: icoCogs, label: "D2", title: "Herramienta", sub: "FastAPI + React · 8 classifiers" },
      { icon: icoShield, label: "D3", title: "Reporte de riesgo", sub: "11 frameworks · 87 leaves" },
    ];
    chips.forEach((c, i) => {
      const y = 1.2 + i * 1.8;
      s.addShape(pres.shapes.RECTANGLE, {
        x: SLIDE_W - 4.2, y, w: 3.7, h: 1.5,
        fill: { color: NAVY_DEEP }, line: { color: ICE, width: 0.75 },
      });
      s.addImage({ data: c.icon, x: SLIDE_W - 4.0, y: y + 0.25, w: 0.45, h: 0.45 });
      s.addText(c.label, {
        x: SLIDE_W - 3.4, y: y + 0.18, w: 1.2, h: 0.5,
        fontFace: HEADER_FONT, fontSize: 22, bold: true, color: CORAL, margin: 0,
      });
      s.addText(c.title, {
        x: SLIDE_W - 4.0, y: y + 0.78, w: 3.4, h: 0.4,
        fontFace: BODY_FONT, fontSize: 16, bold: true, color: WHITE, margin: 0,
      });
      s.addText(c.sub, {
        x: SLIDE_W - 4.0, y: y + 1.12, w: 3.4, h: 0.35,
        fontFace: BODY_FONT, fontSize: 11, color: ICE, margin: 0,
      });
    });

    // Footer
    s.addText("Repositorio:  github.com/reynierortegabueno86/intellintents  ·  rama feature/hierarchical-intent-display", {
      x: 0.7, y: 7.05, w: 12, h: 0.3,
      fontFace: BODY_FONT, fontSize: 10, color: SLATE_LIGHT, margin: 0,
    });
  }

  // ========== SLIDE 2 — TRES ENTREGABLES ==========
  {
    const s = pres.addSlide();
    s.background = { color: PAPER };

    // Title row
    s.addText("Tres entregables, un único hilo", {
      x: 0.6, y: 0.45, w: 12.0, h: 0.7,
      fontFace: HEADER_FONT, fontSize: 36, bold: true, color: NAVY, margin: 0,
    });
    s.addText("Reproducir el hallazgo titular — 81.5% suitability gap — corriendo D2 sobre D1 con la guía de D3.", {
      x: 0.6, y: 1.15, w: 12.0, h: 0.4,
      fontFace: BODY_FONT, fontSize: 14, italic: true, color: SLATE, margin: 0,
    });

    // Three cards
    const cards = [
      {
        code: "D1",
        title: "Dataset anotado",
        icon: icoDB,
        color: NAVY,
        stats: [
          ["146,127", "conversaciones"],
          ["514,814", "turns clasificados"],
          ["246K / 268K", "user / assistant"],
        ],
        bullets: [
          "Corpus español-ES, firma de inversión real",
          "Taxonomía FII v1 · 87 leaf intents",
          "Schema: Dataset → Conversation → Turn → Classification",
          "Custodia: solo local · no nube · no compartido",
        ],
        status: "Existe · custodia única en workstation del lead",
      },
      {
        code: "D2",
        title: "Herramienta IntellIntents",
        icon: icoCogs,
        color: TEAL,
        stats: [
          ["8", "clasificadores"],
          ["2-stage", "cascading default"],
          ["10/10", "test suites verdes"],
        ],
        bullets: [
          "Backend FastAPI · Frontend React/Vite",
          "Cascading + cascading-context (gpt-5.2)",
          "LLM cache SQLite · runs pausables/reanudables",
          "Pipeline: dataset → run → analytics → export",
        ],
        status: "En main · pendiente tag v1.0.0",
      },
      {
        code: "D3",
        title: "Reporte de riesgo regulatorio",
        icon: icoShield,
        color: CORAL,
        stats: [
          ["11", "frameworks cubiertos"],
          ["87", "leaves mapeados"],
          ["4 capas", "trigger framework"],
        ],
        bullets: [
          "MiFID II · RIS · PRIIPs · SFDR · GDPR · AML",
          "Hard / conditional / latent / operacional",
          "Mapping intent → artículo regulatorio",
          "Breaches reales + rewrites compliant",
        ],
        status: "Borrador 980 líneas · pendiente firma",
      },
    ];

    const cardW = 4.0, cardH = 5.4, gap = 0.25;
    const totalW = cardW * 3 + gap * 2;
    const startX = (SLIDE_W - totalW) / 2;
    const cardY = 1.7;

    cards.forEach((c, i) => {
      const x = startX + i * (cardW + gap);
      // Card background
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: cardY, w: cardW, h: cardH,
        fill: { color: WHITE },
        line: { color: "E2E8F0", width: 0.75 },
        shadow: { type: "outer", color: "0F172A", blur: 8, offset: 2, angle: 90, opacity: 0.08 },
      });
      // Top accent strip
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: cardY, w: cardW, h: 0.12,
        fill: { color: c.color }, line: { color: c.color, width: 0 },
      });
      // Header band
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: cardY + 0.12, w: cardW, h: 1.1,
        fill: { color: c.color }, line: { color: c.color, width: 0 },
      });
      s.addImage({ data: c.icon, x: x + 0.3, y: cardY + 0.35, w: 0.6, h: 0.6 });
      s.addText(c.code, {
        x: x + 1.05, y: cardY + 0.22, w: 1.0, h: 0.45,
        fontFace: HEADER_FONT, fontSize: 24, bold: true, color: WHITE, margin: 0,
      });
      s.addText(c.title, {
        x: x + 1.05, y: cardY + 0.65, w: cardW - 1.2, h: 0.5,
        fontFace: BODY_FONT, fontSize: 14, bold: true, color: WHITE, margin: 0,
      });

      // Stats row
      const statsY = cardY + 1.4;
      c.stats.forEach((st, k) => {
        const sx = x + 0.15 + k * ((cardW - 0.3) / 3);
        s.addText(st[0], {
          x: sx, y: statsY, w: (cardW - 0.3) / 3, h: 0.45,
          fontFace: HEADER_FONT, fontSize: 18, bold: true, color: NAVY,
          align: "center", margin: 0,
        });
        s.addText(st[1], {
          x: sx, y: statsY + 0.45, w: (cardW - 0.3) / 3, h: 0.3,
          fontFace: BODY_FONT, fontSize: 9, color: SLATE,
          align: "center", margin: 0,
        });
      });

      // Divider
      s.addShape(pres.shapes.LINE, {
        x: x + 0.3, y: cardY + 2.3, w: cardW - 0.6, h: 0,
        line: { color: "E2E8F0", width: 0.75 },
      });

      // Bullets
      const bulletItems = c.bullets.map((b, k) => ({
        text: b,
        options: { bullet: { code: "25A0" }, breakLine: k < c.bullets.length - 1 },
      }));
      s.addText(bulletItems, {
        x: x + 0.3, y: cardY + 2.45, w: cardW - 0.6, h: 2.2,
        fontFace: BODY_FONT, fontSize: 11, color: INK,
        paraSpaceAfter: 4, margin: 0,
      });

      // Status footer
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: cardY + cardH - 0.55, w: cardW, h: 0.55,
        fill: { color: "F1F5F9" }, line: { color: "F1F5F9", width: 0 },
      });
      s.addText(c.status, {
        x: x + 0.3, y: cardY + cardH - 0.5, w: cardW - 0.6, h: 0.45,
        fontFace: BODY_FONT, fontSize: 10, italic: true, color: SLATE, margin: 0,
      });
    });

    // Footer note
    s.addText("Política de custodia: el dataset permanece local en la workstation del project lead — no commit, no cloud, no shared (16-may-2026)", {
      x: 0.6, y: 7.15, w: 12.0, h: 0.3,
      fontFace: BODY_FONT, fontSize: 10, italic: true, color: SLATE_LIGHT, margin: 0,
    });
  }

  // ========== SLIDE 3 — HALLAZGO TITULAR ==========
  {
    const s = pres.addSlide();
    s.background = { color: PAPER };

    // Title
    s.addText("Hallazgo titular  ·  Suitability gap estructural", {
      x: 0.6, y: 0.45, w: 12.0, h: 0.7,
      fontFace: HEADER_FONT, fontSize: 32, bold: true, color: NAVY, margin: 0,
    });
    s.addText("De cada 100 conversaciones de alto riesgo, 82 carecen de cualquier señal de perfilado MiFID II.", {
      x: 0.6, y: 1.15, w: 12.0, h: 0.4,
      fontFace: BODY_FONT, fontSize: 14, italic: true, color: SLATE, margin: 0,
    });

    // ---- LEFT: Big stat callout ----
    const leftX = 0.6, leftY = 1.85, leftW = 4.6, leftH = 5.0;
    s.addShape(pres.shapes.RECTANGLE, {
      x: leftX, y: leftY, w: leftW, h: leftH,
      fill: { color: NAVY }, line: { color: NAVY, width: 0 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: leftX, y: leftY, w: leftW, h: 0.18,
      fill: { color: CORAL }, line: { color: CORAL, width: 0 },
    });
    s.addImage({ data: icoWarn, x: leftX + 0.3, y: leftY + 0.45, w: 0.45, h: 0.45 });
    s.addText("RIESGO  ·  MiFID II Art. 25(2)", {
      x: leftX + 0.85, y: leftY + 0.5, w: 3.5, h: 0.4,
      fontFace: BODY_FONT, fontSize: 11, bold: true, color: CORAL, charSpacing: 3, margin: 0,
    });

    s.addText("81.5%", {
      x: leftX + 0.1, y: leftY + 1.15, w: leftW - 0.2, h: 1.85,
      fontFace: HEADER_FONT, fontSize: 88, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText("conversaciones de alto riesgo sin señal de suitability", {
      x: leftX + 0.3, y: leftY + 3.1, w: leftW - 0.6, h: 0.6,
      fontFace: BODY_FONT, fontSize: 13, color: ICE,
      align: "center", margin: 0,
    });

    // Supporting micro-stats
    const micro = [
      ["0", "conv con las 5 dim. MiFID II"],
      ["0.0004%", "user turns con preferencia ESG"],
      ["146 K", "conv producción auditadas"],
    ];
    const mY = leftY + 3.9;
    micro.forEach((m, i) => {
      const mx = leftX + 0.2 + i * ((leftW - 0.4) / 3);
      s.addText(m[0], {
        x: mx, y: mY, w: (leftW - 0.4) / 3, h: 0.45,
        fontFace: HEADER_FONT, fontSize: 18, bold: true, color: CORAL,
        align: "center", margin: 0,
      });
      s.addText(m[1], {
        x: mx, y: mY + 0.45, w: (leftW - 0.4) / 3, h: 0.55,
        fontFace: BODY_FONT, fontSize: 9, color: ICE,
        align: "center", margin: 0,
      });
    });

    // ---- RIGHT: bar chart of top 8 high-risk intents and their gap ----
    const chartX = 5.6, chartY = 1.85, chartW = 7.1, chartH = 4.4;
    s.addShape(pres.shapes.RECTANGLE, {
      x: chartX, y: chartY, w: chartW, h: chartH,
      fill: { color: WHITE }, line: { color: "E2E8F0", width: 0.5 },
      shadow: { type: "outer", color: "0F172A", blur: 6, offset: 2, angle: 90, opacity: 0.06 },
    });
    s.addText("Top intents de exposición — % de conversaciones sin señal de suitability", {
      x: chartX + 0.25, y: chartY + 0.2, w: chartW - 0.5, h: 0.35,
      fontFace: BODY_FONT, fontSize: 12, bold: true, color: NAVY, margin: 0,
    });

    const chartData = [{
      name: "Gating gap (%)",
      labels: [
        "transfer_funds",
        "sell_investment",
        "buy_investment",
        "set_recurring_investment",
        "withdraw_funds",
        "request_recommendation",
        "request_rebalance_advice",
        "request_portfolio_suggestion",
      ],
      values: [88.0, 88.0, 83.6, 82.8, 77.0, 49.4, 45.7, 34.1],
    }];
    s.addChart(pres.charts.BAR, chartData, {
      x: chartX + 0.2, y: chartY + 0.65, w: chartW - 0.4, h: chartH - 0.8,
      barDir: "bar",
      chartColors: [CORAL],
      chartArea: { fill: { color: "FFFFFF" }, roundedCorners: false },
      catAxisLabelColor: SLATE,
      catAxisLabelFontFace: BODY_FONT,
      catAxisLabelFontSize: 10,
      valAxisLabelColor: SLATE,
      valAxisLabelFontSize: 9,
      valAxisMinVal: 0,
      valAxisMaxVal: 100,
      valGridLine: { color: "E2E8F0", size: 0.5 },
      catGridLine: { style: "none" },
      showValue: true,
      dataLabelPosition: "outEnd",
      dataLabelFormatCode: '0.0"%"',
      dataLabelColor: NAVY,
      dataLabelFontSize: 9,
      showLegend: false,
    });

    // Bottom insight strip
    s.addShape(pres.shapes.RECTANGLE, {
      x: chartX, y: chartY + chartH + 0.15, w: chartW, h: 0.7,
      fill: { color: NAVY_DEEP }, line: { color: NAVY_DEEP, width: 0 },
    });
    s.addText([
      { text: "Implicación: ", options: { bold: true, color: CORAL } },
      { text: "remediación = priorizar gating sobre los 8 leaves de arriba (cubre ≈80% del riesgo regulatorio del corpus).", options: { color: WHITE } },
    ], {
      x: chartX + 0.25, y: chartY + chartH + 0.22, w: chartW - 0.5, h: 0.55,
      fontFace: BODY_FONT, fontSize: 12, margin: 0,
    });

    // Footer source
    s.addText("Fuente: docs/compliance-risk-analysis.md · run 4 · taxonomía FII v1 · abr-2026", {
      x: 0.6, y: 7.15, w: 12.0, h: 0.3,
      fontFace: BODY_FONT, fontSize: 10, italic: true, color: SLATE_LIGHT, margin: 0,
    });
  }

  // ========== SLIDE 4 — PLAN OPERATIVO + RIESGOS ==========
  {
    const s = pres.addSlide();
    s.background = { color: PAPER };

    s.addText("Plan operativo  ·  4 sprints de 1 semana", {
      x: 0.6, y: 0.45, w: 12.0, h: 0.7,
      fontFace: HEADER_FONT, fontSize: 32, bold: true, color: NAVY, margin: 0,
    });
    s.addText("Definition of Done global: un ingeniero externo reproduce el 81.5% en <1 h leyendo el README.", {
      x: 0.6, y: 1.15, w: 12.0, h: 0.4,
      fontFace: BODY_FONT, fontSize: 14, italic: true, color: SLATE, margin: 0,
    });

    // Timeline strip
    const tlY = 1.95, tlH = 2.55, tlX = 0.6, tlW = 12.1;
    const sprints = [
      { code: "S1", title: "Git cierre + PPTX", out: "PR a main · tag v1.0.0-rc1 · deck firmado", color: NAVY },
      { code: "S2", title: "D3 — reporte", out: "Executive summary · PDF firmado · remediation plan", color: CORAL },
      { code: "S3", title: "D1 — dataset", out: "Dataset card · manifest SHA-256 · sample sintético", color: TEAL },
      { code: "S4", title: "D2 — release", out: "Tag v1.0.0 · demo MP4 · cleanup branches", color: AMBER },
    ];
    const sw = (tlW - 0.4) / 4, sgap = 0.13;
    sprints.forEach((sp, i) => {
      const x = tlX + i * sw;
      const w = sw - sgap;
      // Card
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: tlY, w, h: tlH,
        fill: { color: WHITE }, line: { color: "E2E8F0", width: 0.5 },
        shadow: { type: "outer", color: "0F172A", blur: 6, offset: 2, angle: 90, opacity: 0.08 },
      });
      // Left accent strip
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: tlY, w: 0.1, h: tlH,
        fill: { color: sp.color }, line: { color: sp.color, width: 0 },
      });
      s.addText(sp.code, {
        x: x + 0.25, y: tlY + 0.2, w: w - 0.3, h: 0.5,
        fontFace: HEADER_FONT, fontSize: 22, bold: true, color: sp.color, margin: 0,
      });
      s.addText(sp.title, {
        x: x + 0.25, y: tlY + 0.75, w: w - 0.3, h: 0.5,
        fontFace: BODY_FONT, fontSize: 14, bold: true, color: NAVY, margin: 0,
      });
      // separator
      s.addShape(pres.shapes.LINE, {
        x: x + 0.25, y: tlY + 1.3, w: w - 0.4, h: 0,
        line: { color: "E2E8F0", width: 0.5 },
      });
      s.addText("Salida", {
        x: x + 0.25, y: tlY + 1.4, w: w - 0.3, h: 0.3,
        fontFace: BODY_FONT, fontSize: 9, bold: true,
        color: SLATE, charSpacing: 2, margin: 0,
      });
      s.addText(sp.out, {
        x: x + 0.25, y: tlY + 1.7, w: w - 0.4, h: 0.85,
        fontFace: BODY_FONT, fontSize: 11, color: INK, margin: 0,
      });
    });

    // Risk matrix mini — bottom
    const rY = 4.95, rH = 1.95, rX = 0.6, rW = 12.1;
    s.addText("Riesgos críticos y mitigación", {
      x: rX, y: rY - 0.3, w: rW, h: 0.35,
      fontFace: HEADER_FONT, fontSize: 18, bold: true, color: NAVY, margin: 0,
    });

    const risks = [
      { label: "PII / GDPR breach", level: "Crítico", mit: "Custodia local exclusiva · sin sync cloud · política firmada", color: CORAL },
      { label: "gpt-5.2 deprecation", level: "Alto", mit: "LLM cache SQLite congela respuestas del run 4", color: AMBER },
      { label: "Discrepancia 11/14 cat.", level: "Medio", mit: "Issue dedicado en S4 — reconciliación docs", color: TEAL },
      { label: "Reporte sin firma legal", level: "Crítico", mit: "Versionado v0.9 draft → v1.0 firmado", color: CORAL },
    ];
    const rcW = (rW - 0.3) / 4;
    risks.forEach((r, i) => {
      const x = rX + i * (rcW + 0.1);
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: rY, w: rcW, h: rH,
        fill: { color: WHITE }, line: { color: "E2E8F0", width: 0.5 },
      });
      // Risk pill
      s.addShape(pres.shapes.RECTANGLE, {
        x: x + 0.2, y: rY + 0.2, w: 0.9, h: 0.3,
        fill: { color: r.color }, line: { color: r.color, width: 0 },
      });
      s.addText(r.level.toUpperCase(), {
        x: x + 0.2, y: rY + 0.2, w: 0.9, h: 0.3,
        fontFace: BODY_FONT, fontSize: 9, bold: true, color: WHITE,
        align: "center", valign: "middle", charSpacing: 1, margin: 0,
      });
      s.addText(r.label, {
        x: x + 0.2, y: rY + 0.6, w: rcW - 0.4, h: 0.4,
        fontFace: BODY_FONT, fontSize: 13, bold: true, color: NAVY, margin: 0,
      });
      s.addText(r.mit, {
        x: x + 0.2, y: rY + 1.05, w: rcW - 0.4, h: 0.85,
        fontFace: BODY_FONT, fontSize: 10, color: SLATE, margin: 0,
      });
    });
  }

  // ========== SLIDE 5 — PRÓXIMOS PASOS ==========
  {
    const s = pres.addSlide();
    s.background = { color: NAVY_DEEP };

    // Title
    s.addText("PRÓXIMOS PASOS  ·  24–48H", {
      x: 0.6, y: 0.6, w: 12.0, h: 0.45,
      fontFace: BODY_FONT, fontSize: 12, bold: true,
      color: CORAL, charSpacing: 5, margin: 0,
    });
    s.addText("Cinco acciones para cerrar D1-D2-D3 en el remoto.", {
      x: 0.6, y: 1.05, w: 12.0, h: 0.7,
      fontFace: HEADER_FONT, fontSize: 30, bold: true, color: WHITE, margin: 0,
    });

    // Left column — numbered actions
    const actions = [
      { n: "01", t: "Endurecer .gitignore", d: "Excluir *.jsonl, full_classified_*.json, run_export.json, llm_cache.db*, backend/intellintents.db." },
      { n: "02", t: "Commit de los untracked críticos", d: "docs/, scripts (analyze_databases.py, export_*.py, import_run.py, build_*.js), IntellIntents_Resumen.pptx." },
      { n: "03", t: "Push y abrir PR a main", d: "“Deliverable v1: docs, scripts, executive deck”. Pasa CI + revisión Compliance lead." },
      { n: "04", t: "Firmar política de custodia", d: "Legal/DPO valida docs/dataset-storage-policy.md · checklist §5 ejecutado en la workstation." },
      { n: "05", t: "Tag v1.0.0-rc1 + Steering", d: "Distribuir este deck. Comprometer fecha de v1.0.0 GA al final de S4." },
    ];

    const aX = 0.6, aY = 2.0, aW = 7.4, rowH = 0.84;
    actions.forEach((a, i) => {
      const y = aY + i * rowH;
      s.addText(a.n, {
        x: aX, y, w: 0.85, h: 0.72,
        fontFace: HEADER_FONT, fontSize: 28, bold: true, color: CORAL, margin: 0,
      });
      s.addText(a.t, {
        x: aX + 0.9, y: y, w: aW - 0.95, h: 0.35,
        fontFace: BODY_FONT, fontSize: 14, bold: true, color: WHITE, margin: 0,
      });
      s.addText(a.d, {
        x: aX + 0.9, y: y + 0.35, w: aW - 0.95, h: 0.45,
        fontFace: BODY_FONT, fontSize: 10.5, color: ICE, margin: 0,
      });
    });

    // Right column — git state card
    const gX = 8.3, gY = 2.0, gW = 4.4, gH = 4.3;
    s.addShape(pres.shapes.RECTANGLE, {
      x: gX, y: gY, w: gW, h: gH,
      fill: { color: NAVY }, line: { color: ICE, width: 0.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: gX, y: gY, w: gW, h: 0.12,
      fill: { color: CORAL }, line: { color: CORAL, width: 0 },
    });
    s.addImage({ data: icoGit, x: gX + 0.3, y: gY + 0.35, w: 0.55, h: 0.55 });
    s.addText("ESTADO  GIT", {
      x: gX + 0.95, y: gY + 0.4, w: gW - 1.0, h: 0.45,
      fontFace: BODY_FONT, fontSize: 12, bold: true, color: ICE, charSpacing: 4, margin: 0,
    });

    const gitRows = [
      ["Remoto", "github.com/reynierortegabueno86/\nintellintents", TEAL, "ALCANZABLE"],
      ["Rama", "feature/hierarchical-intent-display", ICE, "ACTIVA"],
      ["Tracked", "103 archivos", ICE, ""],
      ["Untracked críticos", "docs/ · 6 scripts · PPTX", AMBER, "POR COMMIT"],
      ["Dataset", "3.4 GB · solo local", CORAL, "NO COMMIT"],
    ];
    gitRows.forEach((r, i) => {
      const ry = gY + 1.05 + i * 0.62;
      s.addText(r[0].toUpperCase(), {
        x: gX + 0.3, y: ry, w: gW - 0.6, h: 0.22,
        fontFace: BODY_FONT, fontSize: 9, bold: true, color: SLATE_LIGHT, charSpacing: 2, margin: 0,
      });
      s.addText(r[1], {
        x: gX + 0.3, y: ry + 0.22, w: gW - 1.8, h: 0.45,
        fontFace: BODY_FONT, fontSize: 11, color: WHITE, margin: 0,
      });
      if (r[3]) {
        s.addShape(pres.shapes.RECTANGLE, {
          x: gX + gW - 1.45, y: ry + 0.28, w: 1.15, h: 0.3,
          fill: { color: r[2] }, line: { color: r[2], width: 0 },
        });
        s.addText(r[3], {
          x: gX + gW - 1.45, y: ry + 0.28, w: 1.15, h: 0.3,
          fontFace: BODY_FONT, fontSize: 8, bold: true,
          color: r[2] === ICE || r[2] === AMBER ? NAVY_DEEP : WHITE,
          align: "center", valign: "middle", charSpacing: 1, margin: 0,
        });
      }
    });

    // Bottom call-to-action band
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0, y: SLIDE_H - 0.7, w: SLIDE_W, h: 0.7,
      fill: { color: CORAL }, line: { color: CORAL, width: 0 },
    });
    s.addText("Hector Garcia  ·  Project Lead  ·  hgarcia@gptadvisor.com  ·  16-mayo-2026", {
      x: 0.6, y: SLIDE_H - 0.65, w: SLIDE_W - 1.2, h: 0.6,
      fontFace: BODY_FONT, fontSize: 13, bold: true, color: WHITE,
      align: "center", valign: "middle", charSpacing: 2, margin: 0,
    });
  }

  await pres.writeFile({ fileName: "IntellIntents_Deliverables_v1.pptx" });
  console.log("Wrote IntellIntents_Deliverables_v1.pptx");
}

build().catch((e) => {
  console.error(e);
  process.exit(1);
});
