import React, { useState, useEffect } from 'react';
import { PhoneCall, Radio, Filter, RefreshCw, Layers, PhoneIncoming, PhoneOff } from 'lucide-react';
import api from '../services/api';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';

export default function Calls({ showToast }) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modeFilter, setModeFilter] = useState('ALL');
  const [stateFilter, setStateFilter] = useState('ALL');

  const fetchCalls = async () => {
    try {
      setLoading(true);
      const data = await api.getCalls();
      setCalls(data);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to fetch calls: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, []);

  // Filtered dataset
  const filteredCalls = calls.filter((call) => {
    const matchMode = modeFilter === 'ALL' || call.dialing_mode?.toLowerCase() === modeFilter.toLowerCase();
    const matchState = stateFilter === 'ALL' || call.state === stateFilter;
    return matchMode && matchState;
  });

  const columns = [
    {
      key: 'id',
      label: 'Call ID',
      sortable: true,
      className: 'font-mono text-slate-400 w-20',
      render: (id) => <span className="font-semibold text-slate-300">#{id}</span>,
    },
    {
      key: 'agent_id',
      label: 'Allocated Agent',
      sortable: true,
      className: 'font-mono text-slate-300',
      render: (agentId) => (
        <span className="inline-flex items-center gap-1.5 rounded bg-slate-800/80 px-2 py-0.5 text-xs text-indigo-300 border border-slate-700">
          Agent #{agentId}
        </span>
      ),
    },
    {
      key: 'borrower_id',
      label: 'Borrower ID',
      sortable: true,
      className: 'font-mono text-slate-300',
      render: (borrowerId) => (
        <span className="inline-flex items-center gap-1.5 rounded bg-slate-800/80 px-2 py-0.5 text-xs text-cyan-300 border border-slate-700">
          Borrower #{borrowerId}
        </span>
      ),
    },
    {
      key: 'state',
      label: 'Call State',
      sortable: true,
      render: (state) => <StatusBadge status={state} />,
    },
    {
      key: 'provider_call_id',
      label: 'Carrier Reference',
      className: 'font-mono text-xs text-slate-400',
      render: (pid) =>
        pid ? (
          <span className="text-slate-300 bg-[#0B0F17] px-2 py-1 rounded border border-slate-800">
            {pid}
          </span>
        ) : (
          <span className="text-slate-600 italic">Pending carrier ID</span>
        ),
    },
    {
      key: 'dialing_mode',
      label: 'Dialer Mode',
      sortable: true,
      render: (mode) => (
        <span
          className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-mono uppercase font-semibold ${
            mode === 'predictive'
              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
              : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
          }`}
        >
          {mode || 'progressive'}
        </span>
      ),
    },
  ];

  // Distinct states for filter dropdown
  const uniqueStates = Array.from(new Set(calls.map((c) => c.state)));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <PhoneCall className="h-5 w-5 text-indigo-400" />
            Outbound Call Sessions
          </h2>
          <p className="text-xs text-slate-400">
            Comprehensive audit log of active, ringing, connected, and completed dialer calls.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Mode selector */}
          <div className="flex items-center rounded-lg border border-slate-800 bg-[#111827] p-1 text-xs">
            <button
              onClick={() => setModeFilter('ALL')}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                modeFilter === 'ALL' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              All Modes
            </button>
            <button
              onClick={() => setModeFilter('progressive')}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                modeFilter === 'progressive' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Progressive
            </button>
            <button
              onClick={() => setModeFilter('predictive')}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                modeFilter === 'predictive' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Predictive
            </button>
          </div>

          {/* State selector */}
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="rounded-lg border border-slate-800 bg-[#111827] px-3 py-1.5 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
          >
            <option value="ALL">All States ({calls.length})</option>
            {uniqueStates.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Calls Data Table */}
      <DataTable
        columns={columns}
        data={filteredCalls}
        loading={loading}
        searchPlaceholder="Search calls by ID, agent, borrower, or carrier ref..."
        emptyTitle="No calls recorded"
        emptyMessage="Trigger a dialing cycle from the Dashboard or Dialer Control page."
      />
    </div>
  );
}
