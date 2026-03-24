import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getIntentColor } from '../utils/colors';
import { cleanHtml } from '../utils/cleanHtml';
import { formatIntentCompact } from '../utils/formatCategoryName';

export default function ConversationGraph({ data, intentHierarchy = {} }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 400;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const nodes = (data.nodes || []).map((n, i) => ({
      ...n,
      id: n.id ?? i,
      label: n.label ?? `Turn ${n.turn_index ?? i + 1}`,
      intent: n.intent || 'unknown',
      text: cleanHtml(n.text || ''),
    }));

    const links = (data.edges || data.links || []).map((l) => ({
      source: l.source,
      target: l.target,
    }));

    if (!nodes.length) return;

    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'rgba(148, 163, 184, 0.4)');

    const g = svg.append('g');

    const zoom = d3.zoom()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(70))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(20));

    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', 'rgba(148, 163, 184, 0.3)')
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)');

    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', 14)
      .attr('fill', (d) => getIntentColor(intentHierarchy[d.intent] || d.intent))
      .attr('stroke', (d) => getIntentColor(intentHierarchy[d.intent] || d.intent))
      .attr('stroke-width', 3)
      .attr('stroke-opacity', 0.3)
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    const label = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text((d) => d.turn_index ?? d.id)
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('fill', 'white')
      .attr('font-size', '10px')
      .attr('font-weight', '600')
      .attr('pointer-events', 'none');

    node
      .on('mouseover', (event, d) => {
        setTooltip({
          x: event.pageX,
          y: event.pageY,
          label: d.label,
          intent: d.intent,
          text: d.text?.length > 100 ? d.text.slice(0, 100) + '...' : d.text,
        });
      })
      .on('mouseout', () => setTooltip(null));

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y);
      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);
      label.attr('x', (d) => d.x).attr('y', (d) => d.y);
    });

    return () => simulation.stop();
  }, [data]);

  return (
    <div ref={containerRef} className="relative w-full h-[400px] bg-slate-950/50 rounded-xl overflow-hidden">
      <svg ref={svgRef} className="w-full h-full" />
      {tooltip && (
        <div
          className="fixed z-50 glass-card px-3 py-2 text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-semibold text-white">{tooltip.label}</div>
          <div className="text-cyan-400">{formatIntentCompact(tooltip.intent, intentHierarchy)}</div>
          {tooltip.text && <div className="text-slate-400 mt-1 max-w-[200px]">{tooltip.text}</div>}
        </div>
      )}
    </div>
  );
}
