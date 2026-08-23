import React, { useState, useEffect } from 'react';
import {
  Cpu,
  ShieldCheck,
  Zap,
  Server,
  RefreshCw,
  Sparkles,
  Info,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import api from '../services/api';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Predictive({ showToast }) {
  const [provider, setProvider] = useState('a');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchRecommendation = async (prov = provider) => {
    try {
      setLoading(true);
      const res = await api.getPredictiveRecommendation(prov);
      setData(res);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to compute predictive recommendation: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendation(provider);
  }, [provider]);

  const rec = data?.recommendation;
  const safety = data?.safety_decision;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Cpu className="h-5 w-5 text-purple-400" />
            Predictive Pacing & Safety Controller Engine
          </h2>
          <p className="text-xs text-slate-400">
            Real-time pipeline-fill mathematical estimation verified against Safety Controller boundaries.
          </p>
        </div>

        {/* Carrier switcher */}
        <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-[#111827] p-1.5 shadow-sm">
          <span className="px-2 text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
            Carrier:
          </span>
          <button
            onClick={() => setProvider('a')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              provider === 'a'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Server className="h-3.5 w-3.5" />
            Provider A (Reliable)
          </button>
          <button
            onClick={() => setProvider('b')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              provider === 'b'
                ? 'bg-amber-600 text-white shadow-md shadow-amber-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Server className="h-3.5 w-3.5" />
            Provider B (Chaotic)
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-12">
          <LoadingSpinner message="Querying Predictive Pacing Engine & Safety Controller..." size="lg" />
        </div>
      ) : data ? (
        <div className="space-y-6">
          {/* Main Decision Cards */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Recommendation Box */}
            <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/30 via-slate-900/60 to-[#0B0F17] p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-purple-500/20">
                <div className="flex items-center gap-2 text-purple-300 font-semibold text-xs uppercase tracking-wider font-mono">
                  <Cpu className="h-4 w-4 text-purple-400" />
                  Stage 1: Pacing Engine Output
                </div>
                <span className="rounded-full bg-purple-500/10 border border-purple-500/20 px-2.5 py-0.5 text-xs font-mono text-purple-300">
                  Recommended Only
                </span>
              </div>

              <div>
                <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                  Recommended Calls to Initiate
                </span>
                <div className="mt-1 flex items-baseline gap-3">
                  <span className="text-5xl font-extrabold text-purple-400 font-mono">
                    {rec?.recommended_calls ?? 0}
                  </span>
                  <span className="text-xs text-slate-400">outbound calls</span>
                </div>
              </div>

              {/* Zero recommendation state banner */}
              {rec?.recommended_calls === 0 && (
                <div className="rounded-xl border border-slate-800 bg-[#0B0F17]/90 p-3.5 text-xs text-slate-300 flex items-start gap-2.5">
                  <Info className="h-4 w-4 text-sky-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-white">Pipeline at equilibrium (0 Calls Recommended)</span>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Either no agents are currently available or existing in-flight ringing calls are sufficient to saturate expected capacity.
                    </p>
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1.5 font-mono text-xs text-slate-300">
                <span className="font-semibold text-purple-300 text-[11px] uppercase tracking-wider">
                  Engine Math Rationale:
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed break-words">
                  {rec?.reason}
                </p>
              </div>
            </div>

            {/* Safety Controller Box */}
            <div className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/30 via-slate-900/60 to-[#0B0F17] p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-emerald-500/20">
                <div className="flex items-center gap-2 text-emerald-300 font-semibold text-xs uppercase tracking-wider font-mono">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  Stage 2: Safety Controller Authority
                </div>
                <StatusBadge status={safety?.action} />
              </div>

              <div>
                <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                  Final Approved Call Count
                </span>
                <div className="mt-1 flex items-baseline gap-3">
                  <span className="text-5xl font-extrabold text-emerald-400 font-mono">
                    {safety?.approved_calls ?? 0}
                  </span>
                  <span className="text-xs text-slate-400">safe calls allowed</span>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1.5 font-mono text-xs text-slate-300">
                <span className="font-semibold text-emerald-300 text-[11px] uppercase tracking-wider">
                  Safety Controller Verdict:
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed break-words">
                  {safety?.reason}
                </p>
              </div>
            </div>
          </div>

          {/* Mathematical Pipeline Visualizer Card */}
          <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
              <TrendingUp className="h-4 w-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-white">How the Calculation Works (Interview Reference)</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1">
                <span className="text-[10px] text-slate-500">STEP 1</span>
                <div className="font-bold text-slate-200">Target Connections</div>
                <p className="text-[11px] text-slate-400">
                  <code>available_agents - connected_calls</code>
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1">
                <span className="text-[10px] text-slate-500">STEP 2</span>
                <div className="font-bold text-slate-200">Expected From Ringing</div>
                <p className="text-[11px] text-slate-400">
                  <code>floor(ringing_calls * answer_rate)</code>
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1">
                <span className="text-[10px] text-slate-500">STEP 3</span>
                <div className="font-bold text-slate-200">Pipeline Fill</div>
                <p className="text-[11px] text-slate-400">
                  <code>ceil(still_needed / answer_rate)</code>
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-1">
                <span className="text-[10px] text-slate-500">STEP 4</span>
                <div className="font-bold text-emerald-400">Safety Clamping</div>
                <p className="text-[11px] text-slate-400">
                  <code>min(requested, max_safe, health)</code>
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
