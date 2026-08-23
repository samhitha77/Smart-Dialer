import React, { useState, useEffect } from 'react';
import { UserCheck, UserPlus, UserX, Pause, Play, ShieldAlert, Sparkles, RefreshCw } from 'lucide-react';
import api from '../services/api';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';

export default function Agents({ showToast }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [transitioningId, setTransitioningId] = useState(null);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const data = await api.getAgents();
      setAgents(data);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to fetch agent pool: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleCreateAgent = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      setSubmitting(true);
      const newAgent = await api.createAgent(name.trim());
      showToast?.({
        type: 'success',
        message: `Agent ${newAgent.name} created and set to AVAILABLE!`,
      });
      setName('');
      setIsModalOpen(false);
      await fetchAgents();
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to create agent: ' + err.message,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleTransition = async (agentId, targetState) => {
    try {
      setTransitioningId(agentId);
      const res = await api.transitionAgentState(agentId, targetState);
      showToast?.({
        type: 'success',
        message: `Agent #${agentId} transitioned to ${res.state}`,
      });
      await fetchAgents();
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'State transition rejected: ' + err.message,
      });
    } finally {
      setTransitioningId(null);
    }
  };

  const columns = [
    {
      key: 'id',
      label: 'Agent ID',
      sortable: true,
      className: 'font-mono text-slate-400 w-20',
      render: (id) => `#${id}`,
    },
    {
      key: 'name',
      label: 'Agent Name',
      sortable: true,
      className: 'font-semibold text-white',
      render: (name, a) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-800 text-emerald-400 font-semibold text-xs border border-slate-700">
            {name.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="font-medium text-slate-200">{name}</div>
            <div className="text-[11px] text-slate-500 font-mono">ID: {a.id}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'state',
      label: 'Lifecycle State',
      sortable: true,
      render: (state) => <StatusBadge status={state} size="sm" />,
    },
    {
      key: 'actions',
      label: 'State Actions',
      className: 'text-right',
      render: (_, a) => {
        const isCurrent = transitioningId === a.id;
        return (
          <div className="flex items-center justify-end gap-1.5">
            {a.state === 'AVAILABLE' && (
              <>
                <button
                  onClick={() => handleTransition(a.id, 'PAUSED')}
                  disabled={isCurrent}
                  className="rounded-lg border border-slate-800 bg-[#0B0F17] px-2.5 py-1 text-[11px] text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                >
                  Pause
                </button>
                <button
                  onClick={() => handleTransition(a.id, 'OFFLINE')}
                  disabled={isCurrent}
                  className="rounded-lg border border-slate-800 bg-[#0B0F17] px-2.5 py-1 text-[11px] text-rose-400 hover:bg-rose-950/40 hover:border-rose-800 transition-colors"
                >
                  Offline
                </button>
              </>
            )}

            {a.state === 'PAUSED' && (
              <button
                onClick={() => handleTransition(a.id, 'AVAILABLE')}
                disabled={isCurrent}
                className="rounded-lg border border-emerald-800/40 bg-emerald-950/30 px-2.5 py-1 text-[11px] text-emerald-300 hover:bg-emerald-900/50 transition-colors"
              >
                Resume (Available)
              </button>
            )}

            {a.state === 'OFFLINE' && (
              <button
                onClick={() => handleTransition(a.id, 'AVAILABLE')}
                disabled={isCurrent}
                className="rounded-lg border border-emerald-800/40 bg-emerald-950/30 px-2.5 py-1 text-[11px] text-emerald-300 hover:bg-emerald-900/50 transition-colors"
              >
                Go Available
              </button>
            )}

            {a.state === 'WRAP_UP' && (
              <button
                onClick={() => handleTransition(a.id, 'AVAILABLE')}
                disabled={isCurrent}
                className="rounded-lg border border-indigo-800/40 bg-indigo-950/30 px-2.5 py-1 text-[11px] text-indigo-300 hover:bg-indigo-900/50 transition-colors"
              >
                Finish Wrap-up
              </button>
            )}

            {(a.state === 'RESERVED' || a.state === 'DIALING' || a.state === 'CONNECTED') && (
              <span className="text-[11px] text-slate-500 italic">Call in progress</span>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <UserCheck className="h-5 w-5 text-emerald-400" />
            Agent Pool Management
          </h2>
          <p className="text-xs text-slate-400">
            Control human workforce capacity, manage breaks, and trigger availability state transitions.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-500 transition-all"
        >
          <UserPlus className="h-4 w-4" />
          Add Agent
        </button>
      </div>

      {/* Agents Table */}
      <DataTable
        columns={columns}
        data={agents}
        loading={loading}
        searchPlaceholder="Search agents by name or ID..."
        emptyTitle="No agents registered"
        emptyMessage="Add agents to your team to enable progressive & predictive call allocation."
      />

      {/* Create Agent Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add New Debt Collection Agent"
      >
        <form onSubmit={handleCreateAgent} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Agent Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Agent Alice Johnson"
              className="w-full rounded-lg border border-slate-800 bg-[#0B0F17] px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-emerald-500 focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-slate-500">
              New agents automatically enter AVAILABLE status ready for calls.
            </p>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="rounded-lg border border-slate-800 px-4 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Register Agent'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
