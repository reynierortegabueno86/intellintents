import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getIntentColor } from '../utils/colors';
import { formatIntentCompact } from '../utils/formatCategoryName';

export default function IntentGalaxy({ data, height, intentHierarchy = {} }) {
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

    // Parse data
    const nodes = (data.nodes || []).map((n) => ({
      ...n,
      id: n.id || n.name,
      radius: Math.max(8, Math.sqrt(n.count || n.value || 1) * 4),
    }));

    const nodeIds = new Set(nodes.map((n) => n.id));
    const links = (data.edges || data.links || [])
      .filter((l) => nodeIds.has(l.source?.id || l.source) && nodeIds.has(l.target?.id || l.target))
      .map((l) => ({
        ...l,
        source: l.source?.id || l.source,
        target: l.target?.id || l.target,
        value: l.weight || l.count || l.value || 1,
      }));

    if (!nodes.length) return;

    const maxLink = d3.max(links, (d) => d.value) || 1;

    // Defs for glow
    const defs = svg.append('defs');
    nodes.forEach((n) => {
      const color = getIntentColor(intentHierarchy[n.id] || n.id);
      const grad = defs.append('radialGradient').attr('id', `glow-${n.id.replace(/\s+/g, '-')}`);
      grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.6);
      grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0);
    });

    const g = svg.append('g');

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.3, 5])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(100).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d) => d.radius + 5));

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', 'rgba(148, 163, 184, 0.15)')
      .attr('stroke-width', (d) => Math.max(1, (d.value / maxLink) * 4));

    // Glow circles (behind nodes)
    const glow = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => d.radius * 2.5)
      .attr('fill', (d) => `url(#glow-${d.id.replace(/\s+/g, '-')})`)
      .attr('opacity', 0.4);

    // Nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => getIntentColor(intentHierarchy[d.id] || d.id))
      .attr('stroke', (d) => getIntentColor(intentHierarchy[d.id] || d.id))
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.5)
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Labels
    const label = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text((d) => formatIntentCompact(d.id, intentHierarchy))
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => d.radius + 14)
      .attr('fill', 'rgba(203, 213, 225, 0.7)')
      .attr('font-size', '10px')
      .attr('pointer-events', 'none');

    // Hover interactions
    node
      .on('mouseover', (event, d) => {
        const total = d3.sum(nodes, (n) => n.count || n.value || 0);
        const pct = total > 0 ? (((d.count || d.value || 0) / total) * 100).toFixed(1) : '0';
        setTooltip({
          x: event.pageX,
          y: event.pageY,
          name: d.id,
          count: d.count || d.value || 0,
          percentage: pct,
        });
        node.attr('opacity', (n) => {
          if (n.id === d.id) return 1;
          const connected = links.some(
            (l) => (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)
          );
          return connected ? 0.8 : 0.2;
        });
        link.attr('stroke-opacity', (l) =>
          l.source.id === d.id || l.target.id === d.id ? 0.6 : 0.05
        );
      })
      .on('mouseout', () => {
        setTooltip(null);
        node.attr('opacity', 1);
        link.attr('stroke-opacity', 1);
      });

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);
      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);
      glow.attr('cx', (d) => d.x).attr('cy', (d) => d.y);
      label.attr('x', (d) => d.x).attr('y', (d) => d.y);
    });

    return () => simulation.stop();
  }, [data]);

  return (
    <div ref={containerRef} className="relative w-full bg-slate-950/50 rounded-xl overflow-hidden" style={{ height: height || 400 }}>
      <svg ref={svgRef} className="w-full h-full" />
      {tooltip && (
        <div
          className="fixed z-50 glass-card px-3 py-2 text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="font-semibold text-white">{formatIntentCompact(tooltip.name, intentHierarchy)}</div>
          <div className="text-slate-400">Count: {tooltip.count}</div>
          <div className="text-slate-400">{tooltip.percentage}%</div>
        </div>
      )}
    </div>
  );
}
