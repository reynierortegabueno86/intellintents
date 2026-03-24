import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getIntentColor } from '../utils/colors';
import { formatIntentCompact } from '../utils/formatCategoryName';

export default function IntentHeatmap({ data, intentHierarchy = {} }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const margin = { top: 30, right: 20, bottom: 80, left: 130 };

    // Parse data: expect { intents: [...], turns: [...], matrix: [[...]] } or similar
    const intents = data.intents || data.y_labels || [];
    const turns = data.turns || data.x_labels || [];
    const matrix = data.matrix || data.values || [];

    if (!intents.length || !turns.length) return;

    const cellSize = Math.min(40, (width - margin.left - margin.right) / turns.length);
    const height = margin.top + margin.bottom + intents.length * cellSize;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const maxVal = d3.max(matrix.flat()) || 1;
    const colorScale = d3.scaleSequential()
      .domain([0, maxVal])
      .interpolator(d3.interpolateRgb('rgba(15, 23, 42, 0.8)', '#22d3ee'));

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Cells
    intents.forEach((intent, yi) => {
      (matrix[yi] || []).forEach((val, xi) => {
        g.append('rect')
          .attr('x', xi * cellSize)
          .attr('y', yi * cellSize)
          .attr('width', cellSize - 2)
          .attr('height', cellSize - 2)
          .attr('rx', 3)
          .attr('fill', colorScale(val))
          .attr('stroke', 'rgba(30, 41, 59, 0.5)')
          .attr('stroke-width', 1)
          .attr('cursor', 'pointer')
          .on('mouseover', (event) => {
            setTooltip({
              x: event.pageX,
              y: event.pageY,
              intent,
              turn: turns[xi],
              count: val,
            });
          })
          .on('mouseout', () => setTooltip(null));
      });
    });

    // X labels (turns) — rotated to avoid overlap
    turns.forEach((turn, i) => {
      g.append('text')
        .attr('x', 0)
        .attr('y', 0)
        .attr('transform', `translate(${i * cellSize + cellSize / 2},${intents.length * cellSize + 10}) rotate(-45)`)
        .attr('text-anchor', 'end')
        .attr('fill', 'rgba(148, 163, 184, 0.7)')
        .attr('font-size', '10px')
        .text(turn);
    });

    // Y labels (intents)
    intents.forEach((intent, i) => {
      g.append('text')
        .attr('x', -8)
        .attr('y', i * cellSize + cellSize / 2 + 4)
        .attr('text-anchor', 'end')
        .attr('fill', getIntentColor(intentHierarchy[intent] || intent))
        .attr('font-size', '11px')
        .text(() => { const v = formatIntentCompact(intent, intentHierarchy); return v.length > 20 ? v.slice(0, 20) + '..' : v; });
    });

    // X axis label
    svg.append('text')
      .attr('x', margin.left + (turns.length * cellSize) / 2)
      .attr('y', height - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(148, 163, 184, 0.5)')
      .attr('font-size', '11px')
      .text('Turn Index');
  }, [data]);

  return (
    <div ref={containerRef} className="relative w-full bg-slate-950/50 rounded-xl overflow-auto">
      <svg ref={svgRef} />
      {tooltip && (
        <div
          className="fixed z-50 glass-card px-3 py-2 text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-semibold text-white">{formatIntentCompact(tooltip.intent, intentHierarchy)}</div>
          <div className="text-slate-400">Turn: {tooltip.turn}</div>
          <div className="text-cyan-400">Count: {tooltip.count}</div>
        </div>
      )}
    </div>
  );
}
