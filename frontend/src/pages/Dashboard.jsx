import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  LayoutList,
  ArrowLeftRight,
  Sparkles,
  Hash,
} from 'lucide-react';
import { formatCategoryName } from '../utils/formatCategoryName';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import KPICard from '../components/KPICard';
import IntentGalaxy from '../components/IntentGalaxy';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import { getIntentColor } from '../utils/colors';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card px-3 py-2 text-xs">
      <div className="text-white font-medium">{label}</div>
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

function buildGalaxyFromTransitions(transitions) {
  if (!transitions || !Array.isArray(transitions) || transitions.length === 0) return null;

  const nodeCounts = {};
  const edges = [];

  for (const t of transitions) {
    const src = t.from_intent;
    const tgt = t.to_intent;
    nodeCounts[src] = (nodeCounts[src] || 0) + t.count;
    if (src !== tgt && t.count > 0) {
      edges.push({ source: src, target: tgt, weight: t.count });
    }
  }

  const nodes = Object.entries(nodeCounts).map(([id, count]) => ({ id, count }));
  return { nodes, edges };
}

export default function Dashboard() {
  const { data: datasets, loading: loadingDs } = useApi(api.getDatasets, []);
  const { data: taxonomies, loading: loadingTax } = useApi(api.getTaxonomies, []);
  const { data: experiments } = useApi(api.getExperiments, []);
  const [datasetId, setDatasetId] = useState(null);
  const [taxonomyId, setTaxonomyId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Auto-select: prefer dataset/taxonomy that has experiment runs with data
  useEffect(() => {
    if (!datasets?.length || !taxonomies?.length) { setLoading(false); return; }
    if (datasetId && taxonomyId) return; // already selected

    // Try to find a dataset+taxonomy with completed runs
    const expWithRuns = experiments?.find(e => e.run_count > 0);
    if (expWithRuns) {
      setDatasetId(expWithRuns.dataset_id);
      setTaxonomyId(expWithRuns.taxonomy_id);
    } else {
      setDatasetId(datasets[0].id);
      setTaxonomyId(taxonomies[0].id);
    }
  }, [datasets, taxonomies, experiments]);

  // Fetch analytics when selection changes
  useEffect(() => {
    if (!datasetId || !taxonomyId) return;
    setLoading(true);
    Promise.all([
      api.getAnalyticsSummary(datasetId).catch(() => null),
      api.getAnalyticsDistribution(datasetId, taxonomyId).catch(() => null),
      api.getAnalyticsTransitions(datasetId, taxonomyId).catch(() => null),
    ]).then(([sum, dist, trans]) => {
      setSummary(sum);
      setDistribution(dist);
      setGraphData(buildGalaxyFromTransitions(trans));
      setLoading(false);
    });
  }, [datasetId, taxonomyId]);

  // API returns flat array: [{intent, count, percentage}]
  const distChartData = Array.isArray(distribution)
    ? distribution.map((d) => ({ name: d.intent, count: d.count }))
    : [];

  const kpiData = summary
    ? [
        { title: 'Total Conversations', value: summary.total_conversations ?? 0, icon: MessageSquare, color: 'cyan' },
        { title: 'Total Turns', value: summary.total_turns ?? 0, icon: LayoutList, color: 'violet' },
        { title: 'Avg Turns / Conv', value: summary.avg_turns_per_conversation ?? 0, icon: ArrowLeftRight, color: 'emerald' },
        { title: 'Unique Intents', value: summary.unique_intents ?? 0, icon: Sparkles, color: 'pink' },
        { title: 'Intent Entropy', value: summary.intent_entropy ?? 0, icon: Hash, color: 'orange' },
      ]
    : [];

  const isLoading = loading || loadingDs || loadingTax;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Conversation intelligence overview</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={datasetId || ''}
            onChange={(e) => setDatasetId(Number(e.target.value))}
            className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
          >
            {(datasets || []).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select
            value={taxonomyId || ''}
            onChange={(e) => setTaxonomyId(Number(e.target.value))}
            className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
          >
            {(taxonomies || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
      </div>

      {/* KPI Row */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : kpiData.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {kpiData.map((kpi, i) => (
            <KPICard key={kpi.title} {...kpi} index={i} />
          ))}
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-slate-500">
          <Sparkles className="mx-auto mb-3 text-slate-600" size={32} />
          <p>No data yet. Go to <span className="text-cyan-400">Datasets</span> to upload data or seed demo data.</p>
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Distribution Bar Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-5"
        >
          <h2 className="text-sm font-semibold text-slate-300 mb-4">
            Intent Distribution {distChartData.length > 15 && <span className="text-slate-500 font-normal">(top 15 of {distChartData.length})</span>}
          </h2>
          {isLoading ? (
            <Skeleton className="h-64" />
          ) : distChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={distChartData.slice(0, 15)} margin={{ top: 5, right: 10, bottom: 10, left: 10 }}>
                <XAxis
                  dataKey="name"
                  tick={<AngledTick />}
                  interval={0}
                  height={120}
                  tickLine={false}
                />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distChartData.slice(0, 15).map((entry) => (
                    <Cell key={entry.name} fill={getIntentColor(entry.name)} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
              No distribution data available
            </div>
          )}
        </motion.div>

        {/* Intent Galaxy */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-5"
        >
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Intent Galaxy</h2>
          {isLoading ? (
            <Skeleton className="h-64" />
          ) : graphData && graphData.nodes.length > 0 ? (
            <div className="h-[400px]">
              <IntentGalaxy data={graphData} />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-600 text-sm">
              No graph data available
            </div>
          )}
        </motion.div>
      </div>
    </motion.div>
  );
}
