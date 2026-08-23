import React, { useState } from 'react';
import {
  PhoneForwarded,
  Zap,
  Cpu,
  Shield,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Server,
  Play,
  RotateCcw,
  Sparkles,
  Info,
} from 'lucide-react';
import api from '../services/api';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Dialer({ showToast }) {
  const [provider, setProvider] = useState('a');
  const [progressiveResult, setProgressiveResult] = useState(null);
  const [predictiveResult, setPredictiveResult] = useState(null);
  const [loadingProgressive, setLoadingProgressive] = useState(false);
  const [loadingPredictive, setLoadingPredictive] = useState(false);
  const [history, setHistory] = useState([]);

  const handleRunProgressiveCycle = async () => {
    try {
      setLoadingProgressive(true);
      const res = await api.runProgressiveCycle(provider);
      setProgressiveResult(res);

      setHistory((prev) => [
        {
          id: Date.now(),
          type: 'Progressive Cycle',
          timestamp: new Date().toLocaleTimeString(),
          provider: provider.toUpperCase(),
          summary: `${res.succeeded} succeeded / ${res.attempted} attempted`,
          action: res.safety_action,
          reason: res.safety_reason,
        },
        ...prev.slice(0, 9),
      ]);

      showToast?.({
        type: res.succeeded > 0 ? 'success' : 'info',
        message: `Progressive Cycle executed: ${res.succeeded} calls initiated (${res.safety_action})`,
      });
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Progressive cycle failed: ' + err.message,
      });
    } finally {
      setLoadingProgressive(false);
    }
  };

  const handleGetPredictiveRecommendation = async () => {
    try {
      setLoadingPredictive(true);
      const res = await api.getPredictiveRecommendation(provider);
      setPredictiveResult(res);

      setHistory((prev) => [
        {
          id: Date.now(),
          type: 'Predictive Recommendation',
          timestamp: new Date().toLocaleTimeString(),
          provider: provider.toUpperCase(),
          summary: `${res.recommendation?.recommended_calls} recommended -> ${res.safety_decision?.approved_calls} approved`,
          action: res.safety_decision?.action,
          reason: res.safety_decision?.reason,
        },
        ...prev.slice(0, 9),
      ]);

      showToast?.({
        type: 'info',
        message: `Predictive calculation complete: ${res.recommendation?.recommended_calls} recommended, ${res.safety_decision?.approved_calls} approved.`,
      });
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Predictive recommendation failed: ' + err.message,
      });
    } finally {
      setLoadingPredictive(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Provider Selection Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <PhoneForwarded className="h-5 w-5 text-indigo-400" />
            Dialer Strategy & Pacing Control
          </h2>
          <p className="text-xs text-slate-400">
            Execute progressive cycles or compute predictive pacing recommendations with real-time Safety Controller approval.
          </p>
        </div>

        {/* Provider Switcher */}
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
            Provider A (Fast / 95% Reliable)
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
            Provider B (Chaotic / Flaky)
          </button>
        </div>
      </div>

      {/* Main Two Control Cards */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Progressive Dialer Panel */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl flex flex-col justify-between space-y-5">
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  <Zap className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Progressive Dialing Cycle</h3>
                  <p className="text-xs text-slate-400">Strict 1:1 agent-bound outbound call allocation</p>
                </div>
              </div>
              <span className="rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-0.5 text-xs font-mono text-indigo-300">
                POST /dialer/progressive/cycle
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Finds currently available agents, atomically claims agent and borrower leases, verifies the Safety Controller boundary, and initiates up to approved call count.
            </p>

            {/* Progressive Result Box */}
            {progressiveResult && (
              <div className="mt-4 rounded-xl border border-slate-800 bg-[#0B0F17] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
                    Cycle Execution Output
                  </span>
                  <StatusBadge status={progressiveResult.safety_action} />
                </div>

                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="rounded-lg bg-slate-900 p-2 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono">APPROVED</span>
                    <p className="text-base font-bold text-white font-mono">{progressiveResult.safety_approved}</p>
                  </div>
                  <div className="rounded-lg bg-slate-900 p-2 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono">ATTEMPTED</span>
                    <p className="text-base font-bold text-indigo-400 font-mono">{progressiveResult.attempted}</p>
                  </div>
                  <div className="rounded-lg bg-slate-900 p-2 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono">SUCCEEDED</span>
                    <p className="text-base font-bold text-emerald-400 font-mono">{progressiveResult.succeeded}</p>
                  </div>
                  <div className="rounded-lg bg-slate-900 p-2 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono">FAILED/SKIP</span>
                    <p className="text-base font-bold text-slate-400 font-mono">
                      {progressiveResult.failed + progressiveResult.skipped}
                    </p>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-900/60 p-2.5 text-xs text-slate-400 font-mono border border-slate-800">
                  <strong className="text-slate-200">Safety Reason: </strong>
                  {progressiveResult.safety_reason || 'Cycle evaluated cleanly.'}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleRunProgressiveCycle}
            disabled={loadingProgressive}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-all disabled:opacity-50"
          >
            <Play className={`h-4 w-4 ${loadingProgressive ? 'animate-spin' : ''}`} />
            {loadingProgressive ? 'Executing Progressive Cycle...' : `Run Progressive Cycle (Provider ${provider.toUpperCase()})`}
          </button>
        </div>

        {/* Predictive Recommendation Panel */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl flex flex-col justify-between space-y-5">
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  <Cpu className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Predictive Pacing Engine</h3>
                  <p className="text-xs text-slate-400">Statistical pipeline-fill recommendation</p>
                </div>
              </div>
              <span className="rounded-full bg-purple-500/10 border border-purple-500/20 px-2.5 py-0.5 text-xs font-mono text-purple-300">
                GET /dialer/predictive/recommend
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Evaluates current available agents, in-flight ringing calls, historical answer rates, and carrier health. Passes recommendation directly through the Safety Controller boundary.
            </p>

            {/* Predictive Result Box */}
            {predictiveResult && (
              <div className="mt-4 rounded-xl border border-slate-800 bg-[#0B0F17] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
                    Pacing Decision
                  </span>
                  <StatusBadge status={predictiveResult.safety_decision?.action} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-center">
                  <div className="rounded-lg bg-slate-900 p-3 border border-slate-800">
                    <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                      Engine Recommended
                    </span>
                    <p className="text-2xl font-extrabold text-purple-400 font-mono mt-1">
                      {predictiveResult.recommendation?.recommended_calls ?? 0}
                    </p>
                  </div>
                  <div className="rounded-lg bg-slate-900 p-3 border border-slate-800">
                    <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                      Safety Approved
                    </span>
                    <p className="text-2xl font-extrabold text-emerald-400 font-mono mt-1">
                      {predictiveResult.safety_decision?.approved_calls ?? 0}
                    </p>
                  </div>
                </div>

                <div className="space-y-1.5 rounded-lg bg-slate-900/60 p-2.5 text-xs font-mono border border-slate-800">
                  <div className="text-slate-400 text-[11px]">
                    <strong className="text-slate-200">Calculation: </strong>
                    {predictiveResult.recommendation?.reason}
                  </div>
                  <div className="text-slate-400 text-[11px] pt-1 border-t border-slate-800">
                    <strong className="text-emerald-300">Safety Controller: </strong>
                    {predictiveResult.safety_decision?.reason}
                  </div>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleGetPredictiveRecommendation}
            disabled={loadingPredictive}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-purple-600 py-3 text-xs font-semibold text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 transition-all disabled:opacity-50"
          >
            <Sparkles className={`h-4 w-4 ${loadingPredictive ? 'animate-spin' : ''}`} />
            {loadingPredictive ? 'Computing Recommendation...' : `Query Predictive Pacing (Provider ${provider.toUpperCase()})`}
          </button>
        </div>
      </div>

      {/* Manual Run Execution Audit Log */}
      {history.length > 0 && (
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white">Recent Operator Cycles Audit Log</h3>
            <button
              onClick={() => setHistory([])}
              className="text-xs text-slate-400 hover:text-slate-200 font-medium"
            >
              Clear Log
            </button>
          </div>

          <div className="divide-y divide-slate-800/60 font-mono text-xs">
            {history.map((item) => (
              <div key={item.id} className="py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-slate-500">{item.timestamp}</span>
                  <span className="font-semibold text-slate-200">{item.type}</span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400 border border-slate-700">
                    {item.provider}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-slate-300">{item.summary}</span>
                  <StatusBadge status={item.action} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
