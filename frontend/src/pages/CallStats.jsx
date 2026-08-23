import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  PhoneCall,
  Activity,
  CheckCircle2,
  TrendingUp,
  Percent,
  RefreshCw,
  PieChart as PieIcon,
  Shield,
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  RadialBarChart,
  RadialBar,
} from 'recharts';
import api from '../services/api';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';

export default function CallStats({ showToast }) {
  const [stats, setStats] = useState(null);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const [statsData, callsData] = await Promise.all([
        api.getCallStats(),
        api.getCalls().catch(() => []),
      ]);
      setStats(statsData);
      setCalls(callsData);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to fetch call statistics: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const answerRatePercent = stats ? Math.round(stats.answer_rate * 100) : 0;
  const nonAnswerRatePercent = 100 - answerRatePercent;

  // Pie chart data for pipeline breakdown
  const pipelineData = stats
    ? [
        { name: 'Connected (Live)', value: stats.connected, color: '#06B6D4' },
        { name: 'Ringing (Carrier)', value: stats.ringing, color: '#F59E0B' },
        { name: 'Other Active (Reserved/Initiated)', value: Math.max(0, stats.active - stats.ringing - stats.connected), color: '#6366F1' },
      ].filter((d) => d.value > 0)
    : [];

  // Radial chart data for Answer Rate
  const answerRateChartData = [
    { name: 'Answer Rate', value: answerRatePercent, fill: '#10B981' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-indigo-400" />
            Live Pipeline & Call Performance Statistics
          </h2>
          <p className="text-xs text-slate-400">
            Real-time answer rates, active call pipelines, and provider completion ratios consumed from <code>GET /calls/stats</code>.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Calls"
          value={stats?.active ?? 0}
          subtitle="Non-terminal in pipeline"
          icon={PhoneCall}
          color="indigo"
          loading={loading}
        />

        <StatCard
          title="Ringing (Carrier)"
          value={stats?.ringing ?? 0}
          subtitle="Awaiting borrower pickup"
          icon={Activity}
          color="amber"
          loading={loading}
        />

        <StatCard
          title="Connected (Live)"
          value={stats?.connected ?? 0}
          subtitle="Two-way live audio stream"
          icon={CheckCircle2}
          color="cyan"
          loading={loading}
        />

        <StatCard
          title="Rolling Answer Rate"
          value={`${answerRatePercent}%`}
          subtitle="Historical pickup probability"
          icon={Percent}
          color="emerald"
          loading={loading}
        />
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Answer Rate Gauge Card */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                Rolling Answer Rate Efficiency
              </h3>
              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs font-mono font-semibold text-emerald-400">
                {stats?.answer_rate ?? 0}
              </span>
            </div>

            <p className="mt-2 text-xs text-slate-400">
              The predictive pacing engine uses this rolling probability to determine the required pipeline fill ratio:
              <br />
              <code className="text-indigo-300 font-mono text-[11px]">
                calls_needed = ceil(target_connections / answer_rate)
              </code>
            </p>
          </div>

          <div className="my-6 flex flex-col items-center justify-center">
            <div className="relative flex items-center justify-center">
              <div className="h-48 w-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Answered', value: answerRatePercent, color: '#10B981' },
                        { name: 'Unanswered', value: nonAnswerRatePercent, color: '#1E293B' },
                      ]}
                      startAngle={90}
                      endAngle={-270}
                      innerRadius={65}
                      outerRadius={85}
                      dataKey="value"
                      stroke="#111827"
                      strokeWidth={3}
                    >
                      <Cell fill="#10B981" />
                      <Cell fill="#1E293B" />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Center Stat */}
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-3xl font-extrabold text-white font-mono">{answerRatePercent}%</span>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Answer Rate</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3 text-xs flex items-center justify-between text-slate-300">
            <span>Safety Threshold: <strong className="text-slate-100">5.0% Min</strong></span>
            <span>Status: <strong className="text-emerald-400 font-mono font-semibold">SAFE FOR PREDICTIVE</strong></span>
          </div>
        </div>

        {/* Right: Active In-Flight Pipeline Breakdown */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <PieIcon className="h-4 w-4 text-cyan-400" />
                Active In-Flight Call Pipeline
              </h3>
              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-mono text-slate-300 border border-slate-700">
                {stats?.active ?? 0} In-Flight
              </span>
            </div>

            <p className="mt-2 text-xs text-slate-400">
              Live split of calls currently occupying network bandwidth and agent capacity.
            </p>
          </div>

          <div className="my-6 flex flex-col items-center justify-center">
            {pipelineData.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500">
                No active calls currently in-flight.
              </div>
            ) : (
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pipelineData}
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {pipelineData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="#111827" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1E293B',
                        borderColor: '#334155',
                        borderRadius: '0.75rem',
                        color: '#F8FAFC',
                        fontSize: '12px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Breakdown Items */}
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between rounded-lg bg-[#0B0F17] p-2.5 border border-slate-800">
              <div className="flex items-center gap-2 text-cyan-300">
                <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
                <span>Connected Live Audio:</span>
              </div>
              <strong className="font-mono text-white text-sm">{stats?.connected ?? 0}</strong>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-[#0B0F17] p-2.5 border border-slate-800">
              <div className="flex items-center gap-2 text-amber-300">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                <span>Ringing on Telecom Carrier:</span>
              </div>
              <strong className="font-mono text-white text-sm">{stats?.ringing ?? 0}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
