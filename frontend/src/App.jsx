import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Datasets from './pages/Datasets';
import Taxonomy from './pages/Taxonomy';
import Classification from './pages/Classification';
import Analytics from './pages/Analytics';
import Conversations from './pages/Conversations';
import Experiments from './pages/Experiments';
import TurnSearch from './pages/TurnSearch';

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.25 }}
        className="flex-1"
      >
        <Routes location={location}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/taxonomy" element={<Taxonomy />} />
          <Route path="/classification" element={<Classification />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/experiments" element={<Experiments />} />
          <Route path="/search" element={<TurnSearch />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen animated-bg">
        <Sidebar />
        <main className="flex-1 min-h-screen overflow-y-auto">
          {/* Top bar */}
          <div className="sticky top-0 z-40 glass-panel border-b border-slate-700/50 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-sm text-slate-400">Conversation Intelligence Platform</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-600">v1.0</span>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            <AnimatedRoutes />
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}
