import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getIntentColor, getIntentColorWithAlpha } from '../utils/colors';
import { formatIntentCompact } from '../utils/formatCategoryName';

export default function IntentFlow({ data, intentHierarchy = {} }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 500;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const nodes = data.nodes || [];
    const links = data.links || data.edges || [];
    if (!nodes.length) return;

    // ── Group nodes by layer ──
    const layers = {};
    nodes.forEach((n) => {
      const layer = n.layer ?? n.column ?? 0;
      if (!layers[layer]) layers[layer] = [];
      layers[layer].push({ ...n, layer });
    });

    const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);
    const numLayers = layerKeys.length;
    if (numLayers === 0) return;

    // ── Dynamic margins ──
    // bottom: enough room for rotated labels + axis line
    const margin = { top: 10, right: 16, bottom: 60, left: 16 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Each layer occupies a column; centre bars within the column
    const colWidth = innerWidth / numLayers;
    const nodeWidth = Math.min(18, Math.max(10, colWidth * 0.12));
    const nodePad = 4;

    // ── Position nodes proportionally within each column ──
    // First pass: compute raw heights, find which layer is tallest
    const minNodeH = 3;
    const layerRaw = {};
    layerKeys.forEach((layerKey) => {
      const layerNodes = layers[layerKey];
      layerNodes.sort((a, b) => (b.count || 0) - (a.count || 0));
      const totalValue = layerNodes.reduce((s, n) => s + (n.count || n.value || 1), 0);
      const totalPad = Math.max(0, (layerNodes.length - 1) * nodePad);
      const availHeight = innerHeight - totalPad;

      const heights = layerNodes.map((n) => {
        const val = n.count || n.value || 1;
        return Math.max(minNodeH, (val / totalValue) * availHeight);
      });
      const stackedH = heights.reduce((a, b) => a + b, 0) + totalPad;
      layerRaw[layerKey] = { heights, stackedH };
    });

    // If any layer overflows, scale everything down uniformly
    const maxStacked = Math.max(...Object.values(layerRaw).map((l) => l.stackedH));
    const scaleFactor = maxStacked > innerHeight ? innerHeight / maxStacked : 1;

    const nodeMap = {};
    layerKeys.forEach((layerKey, li) => {
      const layerNodes = layers[layerKey];
      const { heights } = layerRaw[layerKey];
      const scaledPad = nodePad * scaleFactor;

      let y = margin.top;
      layerNodes.forEach((n, ni) => {
        const nodeHeight = heights[ni] * scaleFactor;
        const nodeId = n.id || n.name;
        const x = margin.left + li * colWidth + (colWidth - nodeWidth) / 2;
        nodeMap[`${layerKey}-${nodeId}`] = {
          ...n,
          x,
          y,
          width: nodeWidth,
          height: nodeHeight,
          nodeId,
          layerKey,
          sourceOffset: 0,
          targetOffset: 0,
        };
        y += nodeHeight + scaledPad;
      });
    });

    // ── Link thickness scale ──
    const allValues = links.map((l) => l.value || l.count || l.weight || 1);
    const maxVal = d3.max(allValues) || 1;
    // Cap max thickness relative to available space
    const maxThickness = Math.min(20, innerHeight * 0.08);
    const thicknessScale = d3.scaleSqrt().domain([0, maxVal]).range([1, maxThickness]);

    // Sort links so large flows draw first (beneath small ones)
    const sortedLinks = [...links].sort((a, b) => (b.value || 0) - (a.value || 0));

    // ── Precompute link paths with stacking ──
    const linkData = [];
    sortedLinks.forEach((link) => {
      const sourceKey = `${link.source_layer ?? 0}-${link.source}`;
      const targetKey = `${link.target_layer ?? 1}-${link.target}`;
      const source = nodeMap[sourceKey];
      const target = nodeMap[targetKey];
      if (!source || !target) return;

      const val = link.value || link.count || link.weight || 1;
      const thickness = thicknessScale(val);

      // Clamp offsets so links don't overflow the node bar
      const sy = Math.min(
        source.y + source.height - thickness / 2,
        source.y + source.sourceOffset + thickness / 2
      );
      source.sourceOffset += thickness + 0.5;
      const ty = Math.min(
        target.y + target.height - thickness / 2,
        target.y + target.targetOffset + thickness / 2
      );
      target.targetOffset += thickness + 0.5;

      linkData.push({ link, source, target, val, thickness, sy, ty });
    });

    // ── Defs: drop-shadow for nodes ──
    const defs = svg.append('defs');
    const filter = defs.append('filter').attr('id', 'node-glow');
    filter.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'blur');
    filter.append('feComposite').attr('in', 'SourceGraphic').attr('in2', 'blur').attr('operator', 'over');

    const g = svg.append('g');

    // ── Draw links ──
    const linkGroup = g.append('g');
    linkData.forEach(({ source, target, val, thickness, sy, ty }) => {
      const x0 = source.x + nodeWidth;
      const x1 = target.x;
      const cpx = (x0 + x1) / 2;
      const color = getIntentColor(intentHierarchy[source.nodeId] || source.nodeId);

      linkGroup
        .append('path')
        .attr('d', `M${x0},${sy} C${cpx},${sy} ${cpx},${ty} ${x1},${ty}`)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', thickness)
        .attr('stroke-opacity', 0.3)
        .attr('stroke-linecap', 'butt')
        .style('cursor', 'pointer')
        .style('transition', 'stroke-opacity 0.15s')
        .on('mouseover', function (event) {
          d3.select(this).attr('stroke-opacity', 0.7);
          setTooltip({
            x: event.pageX,
            y: event.pageY,
            type: 'link',
            source: formatIntentCompact(source.nodeId, intentHierarchy),
            target: formatIntentCompact(target.nodeId, intentHierarchy),
            value: val,
            color,
          });
        })
        .on('mouseout', function () {
          d3.select(this).attr('stroke-opacity', 0.3);
          setTooltip(null);
        });
    });

    // ── Draw nodes ──
    const nodeGroup = g.append('g');
    Object.values(nodeMap).forEach((n) => {
      const color = getIntentColor(intentHierarchy[n.nodeId] || n.nodeId);

      // Glow background
      nodeGroup
        .append('rect')
        .attr('x', n.x - 1)
        .attr('y', n.y - 1)
        .attr('width', n.width + 2)
        .attr('height', n.height + 2)
        .attr('rx', 3)
        .attr('fill', color)
        .attr('opacity', 0.15)
        .attr('filter', 'url(#node-glow)');

      // Main bar
      nodeGroup
        .append('rect')
        .attr('x', n.x)
        .attr('y', n.y)
        .attr('width', n.width)
        .attr('height', n.height)
        .attr('rx', 2)
        .attr('fill', color)
        .attr('opacity', 0.85)
        .style('cursor', 'pointer')
        .on('mouseover', (event) => {
          setTooltip({
            x: event.pageX,
            y: event.pageY,
            type: 'node',
            name: formatIntentCompact(n.nodeId, intentHierarchy),
            count: n.count || n.value || 0,
            color,
          });
        })
        .on('mouseout', () => setTooltip(null));
    });

    // ── X-axis line ──
    const axisLineY = margin.top + innerHeight + 8;
    g.append('line')
      .attr('x1', margin.left)
      .attr('x2', margin.left + innerWidth)
      .attr('y1', axisLineY)
      .attr('y2', axisLineY)
      .attr('stroke', 'rgba(148, 163, 184, 0.15)')
      .attr('stroke-width', 1);

    // ── Turn axis labels — rotated -45deg so they never overlap ──
    layerKeys.forEach((key, i) => {
      const tickX = margin.left + i * colWidth + colWidth / 2;
      // Small tick mark
      g.append('line')
        .attr('x1', tickX)
        .attr('x2', tickX)
        .attr('y1', axisLineY)
        .attr('y2', axisLineY + 4)
        .attr('stroke', 'rgba(148, 163, 184, 0.25)')
        .attr('stroke-width', 1);
      // Rotated label
      g.append('text')
        .attr('x', tickX)
        .attr('y', axisLineY + 10)
        .attr('text-anchor', 'end')
        .attr('transform', `rotate(-45, ${tickX}, ${axisLineY + 10})`)
        .attr('fill', 'rgba(148, 163, 184, 0.6)')
        .attr('font-size', '10px')
        .attr('font-weight', '500')
        .text(`Turn ${key + 1}`);
    });

    return () => svg.selectAll('*').remove();
  }, [data]);

  // ── Render ──
  return (
    <div
      ref={containerRef}
      className="relative w-full h-[650px] bg-slate-950/40 rounded-xl border border-slate-800/40 overflow-hidden"
    >
      <svg ref={svgRef} className="w-full h-full" />

      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{ left: tooltip.x + 16, top: tooltip.y - 16 }}
        >
          <div className="bg-slate-900/95 backdrop-blur border border-slate-700/50 rounded-lg px-3 py-2 shadow-xl text-xs">
            {tooltip.type === 'node' ? (
              <div className="flex items-center gap-2">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: tooltip.color }}
                />
                <div>
                  <div className="text-white font-medium">{tooltip.name}</div>
                  <div className="text-slate-400">{tooltip.count} occurrences</div>
                </div>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-1.5 text-white font-medium">
                  <span
                    className="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                    style={{ backgroundColor: tooltip.color }}
                  />
                  {tooltip.source}
                  <span className="text-slate-500">&rarr;</span>
                  {tooltip.target}
                </div>
                <div className="text-slate-400 mt-0.5">{tooltip.value} transitions</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
