import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getIntentColor } from '../utils/colors';
import { formatCategoryName } from '../utils/formatCategoryName';

export default function IntentFlow({ data }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 450;
    const margin = { top: 20, right: 40, bottom: 20, left: 40 };

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    // Parse: data should have nodes (with layer/column) and links
    const nodes = data.nodes || [];
    const links = data.links || data.edges || [];

    if (!nodes.length) return;

    // Group nodes by layer/column/turn_position
    const layers = {};
    nodes.forEach((n) => {
      const layer = n.layer ?? n.column ?? n.turn_position ?? 0;
      if (!layers[layer]) layers[layer] = [];
      layers[layer].push({ ...n, layer });
    });

    const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);
    const numLayers = layerKeys.length;
    if (numLayers === 0) return;

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const layerWidth = innerWidth / numLayers;
    const nodeWidth = 18;

    // Position nodes
    const nodeMap = {};
    layerKeys.forEach((layerKey, li) => {
      const layerNodes = layers[layerKey];
      const totalValue = layerNodes.reduce((s, n) => s + (n.count || n.value || 1), 0);
      const spacing = 8;
      const totalSpacing = (layerNodes.length - 1) * spacing;
      const availHeight = innerHeight - totalSpacing;

      let y = margin.top;
      layerNodes.forEach((n) => {
        const val = n.count || n.value || 1;
        const nodeHeight = Math.max(10, (val / totalValue) * availHeight);
        const nodeId = n.id || n.name;
        nodeMap[`${layerKey}-${nodeId}`] = {
          ...n,
          x: margin.left + li * layerWidth,
          y,
          width: nodeWidth,
          height: nodeHeight,
          nodeId,
          layerKey,
        };
        y += nodeHeight + spacing;
      });
    });

    const g = svg.append('g');

    // Draw links as curved paths
    links.forEach((link) => {
      const sourceKey = `${link.source_layer ?? link.source_column ?? 0}-${link.source}`;
      const targetKey = `${link.target_layer ?? link.target_column ?? 1}-${link.target}`;
      const source = nodeMap[sourceKey];
      const target = nodeMap[targetKey];

      if (!source || !target) return;

      const val = link.value || link.count || link.weight || 1;
      const sourceColor = getIntentColor(source.nodeId);
      const thickness = Math.max(2, val * 2);

      const x0 = source.x + nodeWidth;
      const y0 = source.y + source.height / 2;
      const x1 = target.x;
      const y1 = target.y + target.height / 2;
      const mx = (x0 + x1) / 2;

      g.append('path')
        .attr('d', `M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1}`)
        .attr('fill', 'none')
        .attr('stroke', sourceColor)
        .attr('stroke-width', thickness)
        .attr('stroke-opacity', 0.25)
        .on('mouseover', function (event) {
          d3.select(this).attr('stroke-opacity', 0.6);
          setTooltip({
            x: event.pageX,
            y: event.pageY,
            text: `${source.nodeId} -> ${target.nodeId}: ${val}`,
          });
        })
        .on('mouseout', function () {
          d3.select(this).attr('stroke-opacity', 0.25);
          setTooltip(null);
        });
    });

    // Draw nodes
    Object.values(nodeMap).forEach((n) => {
      const color = getIntentColor(n.nodeId);
      g.append('rect')
        .attr('x', n.x)
        .attr('y', n.y)
        .attr('width', n.width)
        .attr('height', n.height)
        .attr('rx', 4)
        .attr('fill', color)
        .attr('opacity', 0.8)
        .on('mouseover', (event) => {
          setTooltip({
            x: event.pageX,
            y: event.pageY,
            text: `${n.nodeId} (${n.count || n.value || 0})`,
          });
        })
        .on('mouseout', () => setTooltip(null));

      // Label
      g.append('text')
        .attr('x', n.x + nodeWidth / 2)
        .attr('y', n.y - 4)
        .attr('text-anchor', 'middle')
        .attr('fill', 'rgba(203, 213, 225, 0.6)')
        .attr('font-size', '9px')
        .text(() => { const v = formatCategoryName(n.nodeId); return v.length > 12 ? v.slice(0, 12) + '..' : v; });
    });

    // Layer labels
    layerKeys.forEach((key, i) => {
      g.append('text')
        .attr('x', margin.left + i * layerWidth + nodeWidth / 2)
        .attr('y', height - 4)
        .attr('text-anchor', 'middle')
        .attr('fill', 'rgba(148, 163, 184, 0.5)')
        .attr('font-size', '10px')
        .text(`Turn ${key + 1}`);
    });

    return () => svg.selectAll('*').remove();
  }, [data]);

  return (
    <div ref={containerRef} className="relative w-full h-[450px] bg-slate-950/50 rounded-xl overflow-hidden">
      <svg ref={svgRef} className="w-full h-full" />
      {tooltip && (
        <div
          className="fixed z-50 glass-card px-3 py-2 text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="text-white">{tooltip.text}</div>
        </div>
      )}
    </div>
  );
}
