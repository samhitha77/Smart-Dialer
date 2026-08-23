import React, { useState, useEffect } from 'react';
import {
  Users,
  PhoneCall,
  PhoneForwarded,
  Activity,
  CheckCircle2,
  Radio,
  Sparkles,
  ShieldCheck,
  Zap,
  ArrowRight,
  TrendingUp,
  Cpu,
  RefreshCw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import api from '../services/api';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

export default function Dashboard({ onNavigate, showToast }) {
  const [stats, setStats] = useState(null);
  const [agents, setAgents] = useState([]);
  const [calls, setCalls] = useState([]);
  const [events, setEvents] = useState([]);
  const [borrowers, setBorrowers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsData, agentsData, callsData, eventsData, borrowersData] = await Promise.all([
        api.getCallStats().catch(() => ({ active: 0, ringing: 0, connected: 0, answer_rate: 0 })),
        api.getAgents().catch(() => []),
        api.getCalls().catch(() => []),
        api.getEvents().catch(() => []),
        api.getBorrowers().catch(() => []),
      ]);

      setStats(statsData);
      setAgents(agentsData);
      setCalls(callsData);
      setEvents(eventsData);
      setBorrowers(borrowersData);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to load dashboard metrics: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleQuickProgressiveCycle = async () => {
    try {
      setActionLoading(true);
      const res = await api.runProgressiveCycle('a');
      showToast?.({
        type: res.succeeded > 0 ? 'success' : 'info',
        message: `Cycle Complete: ${res.succeeded} calls started (${res.safety_action}: ${res.safety_reason})`,
      });
      await fetchDashboardData();
    } catch (err) {
      showToast?.({
        type: 'error',
        message: err.message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  // Compute Agent State Distribution
  const availableAgentsCount = agents.filter((a) => a.state === 'AVAILABLE').length;
  const connectedAgentsCount = agents.filter((a) => a.state === 'CONNECTED').length;
  const dialingAgentsCount = agents.filter((a) => a.state === 'DIALING' || a.state === 'RESERVED').length;
  const offlineAgentsCount = agents.filter((a) => a.state === 'OFFLINE' || a.state === 'PAUSED').length;

  const agentPieData = [
    { name: 'Available', value: availableAgentsCount, color: '#10B981' },
    { name: 'Connected', value: connectedAgentsCount, color: '#06B6D4' },
    { name: 'Dialing/Reserved', value: dialingAgentsCount, color: '#6366F1' },
    { name: 'Offline/Paused', value: offlineAgentsCount, color: '#64748B' },
  ].filter((item) => item.value > 0);

  // Compute Call State Breakdown from real calls
  const callStateCounts = calls.reduce((acc, call) => {
    acc[call.state] = (acc[call.state] || 0) + 1;
    return acc;
  }, {});

  const callBarData = Object.entries(callStateCounts).map(([state, count]) => ({
    state,
    count,
  }));

  const answerRatePercent = stats ? Math.round(stats.answer_rate * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Top Banner with Quick Actions */}
      <div className="relative overflow-hidden rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-[#0B0F17] p-6 shadow-xl">
        <div className="absolute right-0 top-0 -mt-8 -mr-8 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />

        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs uppercase tracking-wider font-mono">
              <Sparkles className="h-4 w-4" />
              Smart Dialer Operations Central
            </div>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-white">
              Autonomous Campaign & Safety Orchestration
            </h2>
            <p className="mt-1 max-w-2xl text-xs text-slate-400 leading-relaxed">
              Real-time monitoring of available agent queues, progressive cycle execution,
              predictive pipeline pacing, and provider webhook event idempotency.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleQuickProgressiveCycle}
              disabled={actionLoading}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-all disabled:opacity-50"
            >
              <Zap className={`h-4 w-4 ${actionLoading ? 'animate-spin' : ''}`} />
              Trigger Progressive Cycle
            </button>

            <button
              onClick={() => onNavigate('predictive')}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-all"
            >
              <Cpu className="h-4 w-4 text-cyan-400" />
              Predictive Recommendations
            </button>
          </div>
        </div>
      </div>

      {/* Primary KPI Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard
          title="Available Agents"
          value={availableAgentsCount}
          subtitle={`Out of ${agents.length} total agents`}
          icon={Users}
          color="emerald"
          loading={loading}
          onClick={() => onNavigate('agents')}
        />

        <StatCard
          title="Active Calls"
          value={stats?.active ?? 0}
          subtitle="Non-terminal in pipeline"
          icon={PhoneCall}
          color="indigo"
          loading={loading}
          onClick={() => onNavigate('calls')}
        />

        <StatCard
          title="Ringing Calls"
          value={stats?.ringing ?? 0}
          subtitle="Dialing carrier network"
          icon={Activity}
          color="amber"
          loading={loading}
          onClick={() => onNavigate('calls')}
        />

        <StatCard
          title="Connected Calls"
          value={stats?.connected ?? 0}
          subtitle="Live borrower conversation"
          icon={CheckCircle2}
          color="cyan"
          loading={loading}
          onClick={() => onNavigate('calls')}
        />

        <StatCard
          title="Answer Rate"
          value={`${answerRatePercent}%`}
          subtitle="Rolling completion ratio"
          icon={TrendingUp}
          color="purple"
          loading={loading}
          onClick={() => onNavigate('call-stats')}
        />

        <StatCard
          title="Total Events"
          value={events.length}
          subtitle="Idempotent webhook logs"
          icon={Radio}
          color="rose"
          loading={loading}
          onClick={() => onNavigate('events')}
        />
      </div>

      {/* Middle Section: Visual Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Call Status Distribution */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg lg:col-span-2">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-bold tracking-tight text-white">Call Lifecycle Distribution</h3>
              <p className="text-xs text-slate-400">Total historical calls by state machine status</p>
            </div>
            <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-mono text-slate-300 border border-slate-700">
              {calls.length} Total Calls
            </span>
          </div>

          <div className="mt-4 h-64 w-full">
            {callBarData.length === 0 ? (
              <EmptyState
                title="No calls recorded yet"
                message="Run a Progressive or Predictive dialing cycle to begin tracking calls."
                action={
                  <button
                    onClick={handleQuickProgressiveCycle}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                  >
                    Run First Cycle
                  </button>
                }
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={callBarData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis
                    dataKey="state"
                    stroke="#64748B"
                    fontSize={10}
                    tickLine={false}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                  />
                  <YAxis stroke="#64748B" fontSize={11} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1E293B',
                      borderColor: '#334155',
                      borderRadius: '0.75rem',
                      color: '#F8FAFC',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#6366F1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Right 1 Col: Agent Capacity Donut */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-bold tracking-tight text-white">Agent Capacity</h3>
              <p className="text-xs text-slate-400">Live human resource allocation</p>
            </div>
            <button
              onClick={() => onNavigate('agents')}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
            >
              Manage &rarr;
            </button>
          </div>

          <div className="mt-4 flex flex-col items-center justify-center">
            {agentPieData.length === 0 ? (
              <EmptyState
                title="Agent pool empty"
                message="Create agents to begin dialing."
                action={
                  <button
                    onClick={() => onNavigate('agents')}
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
                  >
                    Add Agents
                  </button>
                }
              />
            ) : (
              <>
                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={agentPieData}
                        innerRadius={50}
                        outerRadius={75}
                        paddingAngle={4}
                        dataKey="value"
                      >
                        {agentPieData.map((entry, index) => (
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

                {/* Legend */}
                <div className="mt-2 grid grid-cols-2 gap-2 w-full text-xs">
                  {agentPieData.map((item) => (
                    <div key={item.name} className="flex items-center gap-2 text-slate-300">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="truncate text-slate-400">{item.name}:</span>
                      <strong className="font-mono text-white">{item.value}</strong>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Section: Recent Events & System Health Overview */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent Webhook Events */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg lg:col-span-2">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-rose-400" />
              <div>
                <h3 className="text-sm font-bold tracking-tight text-white">Recent Telecom Events</h3>
                <p className="text-xs text-slate-400">Idempotency-verified carrier event log</p>
              </div>
            </div>

            <button
              onClick={() => onNavigate('events')}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
            >
              View All Events &rarr;
            </button>
          </div>

          <div className="mt-3 divide-y divide-slate-800/60 overflow-hidden">
            {events.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  title="No webhook events logged"
                  message="Provider events will appear here as calls progress."
                />
              </div>
            ) : (
              events.slice(0, 5).map((evt) => (
                <div key={evt.id} className="flex items-center justify-between py-3 text-xs">
                  <div className="flex items-center gap-3">
                    <StatusBadge status={evt.event_type} />
                    <div>
                      <span className="font-mono text-slate-300 font-medium">{evt.event_id}</span>
                      <p className="text-[11px] text-slate-500">Call ID: {evt.call_id}</p>
                    </div>
                  </div>

                  <div className="text-right font-mono">
                    <span className={evt.processed ? 'text-emerald-400' : 'text-amber-400'}>
                      {evt.processed ? 'PROCESSED' : 'DISCARDED'}
                    </span>
                    {evt.discard_reason && (
                      <p className="text-[10px] text-slate-400 truncate max-w-xs">{evt.discard_reason}</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* System Architecture Boundaries */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-bold tracking-tight text-white">Safety Boundaries</h3>
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>Concurrency Lock</span>
                <span className="text-emerald-400 font-mono">ENFORCED</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Atomic SQL <code>UPDATE WHERE state='AVAILABLE'</code> guarantees single-winner reservations.
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>Safety Controller</span>
                <span className="text-emerald-400 font-mono">STRICT CEILING</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Pure function evaluates hard caps, provider health, and unanswer ratios. Cannot be bypassed.
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>Lease Crash Recovery</span>
                <span className="text-indigo-400 font-mono">60s TIMEOUT</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Stale worker reservations auto-expire back to AVAILABLE without distributed coordination.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
