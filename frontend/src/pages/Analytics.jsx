import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, PieChart, Pie, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import FilterPanel from '../components/FilterPanel';
import IntentGalaxy from '../components/IntentGalaxy';
import IntentFlow from '../components/IntentFlow';
import IntentHeatmap from '../components/IntentHeatmap';
import { getIntentColor } from '../utils/colors';
import { formatCategoryName } from '../utils/formatCategoryName';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

const TABS = ['Distribution', 'Galaxy', 'Flow', 'Heatmap', 'Transitions'];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card px-3 py-2 text-xs">
      <div className="text-white font-medium">{label || payload[0]?.name}</div>
      <div className="text-cyan-400">Count: {payload[0].value}</div>
    </div>
  );
};

const AngledTick = ({ x, y, payload }) => (
  <g transform={`translate(${x},${y})`}>
    <text
      x={0} y={0} dy={10}
      textAnchor="end"
      fill="#94a3b8"
      fontSize={9}
      transform="rotate(-50)"
    >
      {(() => { const v = formatCategoryName(payload.value); return v?.length > 20 ? v.slice(0, 20) + '..' : v; })()}
    </text>
  </g>
);

// Build galaxy {nodes, edges} from flat transitions array
function buildGalaxyFromTransitions(transitions) {
  if (!Array.isArray(transitions) || transitions.length === 0) return null;
  const nodeCounts = {};
  const edges = [];
  for (const t of transitions) {
    nodeCounts[t.from_intent] = (nodeCounts[t.from_intent] || 0) + t.count;
    if (t.count > 0 && t.from_intent !== t.to_intent) {
      edges.push({ source: t.from_intent, target: t.to_intent, weight: t.count });
    }
  }
  const nodes = Object.entries(nodeCounts).map(([id, count]) => ({ id, count }));
  return { nodes, edges };
}

// Build heatmap {intents, turns, matrix} from flat array [{turn_index, intent, count}]
function buildHeatmapMatrix(rawHeatmap) {
  if (!Array.isArray(rawHeatmap) || rawHeatmap.length === 0) return null;
  const intentSet = new Set();
  const turnSet = new Set();
  for (const cell of rawHeatmap) {
    intentSet.add(cell.intent);
    turnSet.add(cell.turn_index);
  }
  const intents = [...intentSet].sort();
  const turns = [...turnSet].sort((a, b) => a - b);
  const turnLabels = turns.map((t) => `Turn ${t + 1}`);

  const matrix = intents.map(() => turns.map(() => 0));
  for (const cell of rawHeatmap) {
    const yi = intents.indexOf(cell.intent);
    const xi = turns.indexOf(cell.turn_index);
    if (yi >= 0 && xi >= 0) matrix[yi][xi] = cell.count;
  }
  return { intents, turns: turnLabels, matrix };
}

// Build flow data from heatmap matrix
function buildFlowFromHeatmap(hm) {
  if (!hm) return null;
  const { intents, turns, matrix } = hm;
  const nodes = [];
  const links = [];

  turns.forEach((turn, ti) => {
    intents.forEach((intent, ii) => {
      const val = matrix[ii]?.[ti] || 0;
      if (val > 0) {
        nodes.push({ id: intent, name: intent, layer: ti, count: val });
      }
    });
  });

  for (let ti = 0; ti < turns.length - 1; ti++) {
    intents.forEach((srcIntent, si) => {
      const srcVal = matrix[si]?.[ti] || 0;
      if (srcVal === 0) return;
      intents.forEach((tgtIntent, tgi) => {
        const tgtVal = matrix[tgi]?.[ti + 1] || 0;
        if (tgtVal > 0) {
          links.push({
            source: srcIntent,
            target: tgtIntent,
            source_layer: ti,
            target_layer: ti + 1,
            value: Math.min(srcVal, tgtVal),
          });
        }
      });
    });
  }
  return { nodes, links };
}

// Build transition matrix table from flat transitions array
function buildTransitionMatrix(transitions) {
  if (!Array.isArray(transitions) || transitions.length === 0) return null;
  const labels = [...new Set(transitions.flatMap((t) => [t.from_intent, t.to_intent]))].sort();
  const matrix = labels.map(() => labels.map(() => 0));
  for (const t of transitions) {
    const ri = labels.indexOf(t.from_intent);
    const ci = labels.indexOf(t.to_intent);
    if (ri >= 0 && ci >= 0) matrix[ri][ci] = t.probability;
  }
  return { labels, matrix };
}

export default function Analytics() {
  const { data: datasets } = useApi(api.getDatasets, []);
  const { data: taxonomies } = useApi(api.getTaxonomies, []);
  const { data: experiments } = useApi(api.getExperiments, []);

  const [datasetId, setDatasetId] = useState(null);
  const [taxonomyId, setTaxonomyId] = useState(null);
  const [tab, setTab] = useState('Distribution');

  const [distribution, setDistribution] = useState(null);
  const [transitions, setTransitions] = useState(null);
  const [rawHeatmap, setRawHeatmap] = useState(null);
  const [loading, setLoading] = useState(false);

  // Auto-select: prefer dataset/taxonomy that has experiment runs with data
  useEffect(() => {
    if (!datasets?.length || !taxonomies?.length) return;
    if (datasetId != null && taxonomyId != null) return;

    const expWithRuns = experiments?.find(e => e.run_count > 0);
    if (expWithRuns) {
      setDatasetId(expWithRuns.dataset_id);
      setTaxonomyId(expWithRuns.taxonomy_id);
    } else {
      setDatasetId(datasets[0].id);
      setTaxonomyId(taxonomies[0].id);
    }
  }, [datasets, taxonomies, experiments]);

  // Fetch data whenever dataset/taxonomy change
  useEffect(() => {
    if (datasetId == null || taxonomyId == null) return;
    setLoading(true);
    Promise.all([
      api.getAnalyticsDistribution(datasetId, taxonomyId).catch(() => null),
      api.getAnalyticsTransitions(datasetId, taxonomyId).catch(() => null),
      api.getAnalyticsHeatmap(datasetId, taxonomyId).catch(() => null),
    ]).then(([dist, trans, hm]) => {
      setDistribution(dist);
      setTransitions(trans);
      setRawHeatmap(hm);
      setLoading(false);
    });
  }, [datasetId, taxonomyId]);

  // Derived data
  const distData = useMemo(() =>
    Array.isArray(distribution)
      ? distribution.map((d) => ({ name: d.intent, count: d.count }))
      : [],
    [distribution]
  );

  const galaxyData = useMemo(() => buildGalaxyFromTransitions(transitions), [transitions]);
  const heatmapData = useMemo(() => buildHeatmapMatrix(rawHeatmap), [rawHeatmap]);
  const flowData = useMemo(() => buildFlowFromHeatmap(heatmapData), [heatmapData]);
  const transTable = useMemo(() => buildTransitionMatrix(transitions), [transitions]);

  const intentLabels = useMemo(() =>
    distData.map((d) => d.name),
    [distData]
  );

  const handleDatasetChange = (val) => setDatasetId(val ? Number(val) : null);
  const handleTaxonomyChange = (val) => setTaxonomyId(val ? Number(val) : null);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="text-sm text-slate-500 mt-1">Deep analysis of intent patterns and transitions</p>
      </div>

      {/* Filter */}
      <FilterPanel
        datasets={datasets || []}
        taxonomies={taxonomies || []}
        intents={intentLabels}
        selectedDataset={datasetId ?? ''}
        selectedTaxonomy={taxonomyId ?? ''}
        onDatasetChange={handleDatasetChange}
        onTaxonomyChange={handleTaxonomyChange}
      />

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-700/50 w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${
              tab === t
                ? 'bg-cyan-400/15 text-cyan-400 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {loading ? (
        <Skeleton className="h-96" />
      ) : (
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {tab === 'Distribution' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Bar Chart — show top 20 intents to avoid overflow */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-4">
                  Bar Chart {distData.length > 20 && <span className="text-slate-500 font-normal">(top 20 of {distData.length})</span>}
                </h3>
                {distData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={420}>
                    <BarChart data={distData.slice(0, 20)} margin={{ top: 5, right: 10, bottom: 10, left: 10 }}>
                      <XAxis
                        dataKey="name"
                        tick={<AngledTick />}
                        interval={0}
                        height={130}
                        tickLine={false}
                      />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {distData.slice(0, 20).map((e) => (
                          <Cell key={e.name} fill={getIntentColor(e.name)} fillOpacity={0.8} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-80 flex items-center justify-center text-slate-600 text-sm">No data</div>
                )}
              </div>

              {/* Pie Chart — show top 10 intents, group rest as "Other" */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-4">Pie Chart</h3>
                {distData.length > 0 ? (() => {
                  const top = distData.slice(0, 10);
                  const rest = distData.slice(10);
                  const pieData = rest.length > 0
                    ? [...top, { name: `Other (${rest.length})`, count: rest.reduce((s, d) => s + d.count, 0) }]
                    : top;
                  return (
                    <ResponsiveContainer width="100%" height={420}>
                      <PieChart>
                        <Pie
                          data={pieData}
                          dataKey="count"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={130}
                          innerRadius={55}
                          paddingAngle={2}
                          label={({ name, percent }) => percent > 0.03 ? `${name.length > 15 ? name.slice(0, 15) + '..' : name} ${(percent * 100).toFixed(0)}%` : ''}
                          labelLine={{ stroke: '#475569' }}
                        >
                          {pieData.map((e) => (
                            <Cell key={e.name} fill={getIntentColor(e.name)} fillOpacity={0.8} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                      </PieChart>
                    </ResponsiveContainer>
                  );
                })() : (
                  <div className="h-80 flex items-center justify-center text-slate-600 text-sm">No data</div>
                )}
              </div>
            </div>
          )}

          {tab === 'Galaxy' && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Intent Galaxy</h3>
              {galaxyData && galaxyData.nodes.length > 0 ? (
                <IntentGalaxy data={galaxyData} height={600} />
              ) : (
                <div className="h-96 flex items-center justify-center text-slate-600 text-sm">
                  No transition data available
                </div>
              )}
            </div>
          )}

          {tab === 'Flow' && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Intent Flow</h3>
              {flowData && flowData.nodes.length > 0 ? (
                <IntentFlow data={flowData} />
              ) : (
                <div className="h-96 flex items-center justify-center text-slate-600 text-sm">
                  No flow data available
                </div>
              )}
            </div>
          )}

          {tab === 'Heatmap' && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Intent Heatmap</h3>
              {heatmapData ? (
                <IntentHeatmap data={heatmapData} />
              ) : (
                <div className="h-96 flex items-center justify-center text-slate-600 text-sm">
                  No heatmap data available
                </div>
              )}
            </div>
          )}

          {tab === 'Transitions' && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Transition Probability Matrix</h3>
              {transTable ? (
                <div className="overflow-x-auto overflow-y-auto max-h-[600px] rounded-lg border border-slate-800/50">
                  <table className="text-xs border-collapse min-w-max">
                    <thead className="sticky top-0 z-10">
                      <tr>
                        <th className="px-3 py-2 text-slate-500 text-left sticky left-0 z-20 bg-slate-900 border-b border-r border-slate-800/50 min-w-[140px]">From / To</th>
                        {transTable.labels.map((l) => (
                          <th key={l} className="px-2 py-2 text-slate-500 font-medium bg-slate-900 border-b border-slate-800/50 whitespace-nowrap" style={{ color: getIntentColor(l) }}
                              title={l}>
                            {l.length > 14 ? l.slice(0, 14) + '..' : l}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {transTable.matrix.map((row, i) => {
                        const maxVal = Math.max(...transTable.matrix.flat().filter(Number.isFinite));
                        return (
                          <tr key={i} className="hover:bg-slate-800/20">
                            <td className="px-3 py-1.5 font-medium sticky left-0 bg-slate-900/95 border-r border-slate-800/50 whitespace-nowrap" style={{ color: getIntentColor(transTable.labels[i]) }}
                                title={transTable.labels[i]}>
                              {transTable.labels[i]?.length > 18 ? transTable.labels[i].slice(0, 18) + '..' : transTable.labels[i]}
                            </td>
                            {row.map((val, j) => {
                              const intensity = maxVal > 0 ? val / maxVal : 0;
                              return (
                                <td
                                  key={j}
                                  className="px-2 py-1.5 text-center font-mono"
                                  style={{
                                    backgroundColor: `rgba(34, 211, 238, ${intensity * 0.4})`,
                                    color: intensity > 0.5 ? 'white' : '#94a3b8',
                                  }}
                                >
                                  {val > 0 ? val.toFixed(2) : '-'}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
                  No transition data available
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
