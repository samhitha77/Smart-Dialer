import React, { useState, useEffect } from 'react';
import {
  Radio,
  Send,
  Sparkles,
  ShieldCheck,
  RefreshCw,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import api from '../services/api';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';

export default function Events({ showToast }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Webhook Simulator Form state
  const [eventId, setEventId] = useState('');
  const [providerCallId, setProviderCallId] = useState('');
  const [eventType, setEventType] = useState('RINGING');
  const [webhookResponse, setWebhookResponse] = useState(null);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const data = await api.getEvents();
      setEvents(data);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to fetch provider events: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    // Pre-populate with sample IDs for convenience
    generateRandomEventId();
  }, []);

  const generateRandomEventId = () => {
    const randomHex = Math.random().toString(16).substring(2, 10).toUpperCase();
    setEventId(`EVT-${randomHex}`);
  };

  const handleSendWebhook = async (e) => {
    e.preventDefault();
    if (!eventId.trim() || !providerCallId.trim()) {
      showToast?.({
        type: 'warning',
        message: 'Please fill in both Event ID and Provider Call ID.',
      });
      return;
    }

    try {
      setSubmitting(true);
      setWebhookResponse(null);
      const res = await api.postProviderWebhook(eventId.trim(), providerCallId.trim(), eventType);
      setWebhookResponse(res);

      if (res.processed) {
        showToast?.({
          type: 'success',
          message: `Event ${eventType} applied to Call #${res.call_id}: ${res.reason}`,
        });
      } else {
        showToast?.({
          type: 'warning',
          message: `Event ${eventType} skipped/discarded: ${res.reason}`,
        });
      }

      await fetchEvents();
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Webhook delivery failed: ' + err.message,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      key: 'event_id',
      label: 'Event Idempotency Key',
      sortable: true,
      className: 'font-mono text-xs font-semibold text-slate-200',
      render: (id) => (
        <span className="bg-[#0B0F17] px-2.5 py-1 rounded border border-slate-800 text-indigo-300">
          {id}
        </span>
      ),
    },
    {
      key: 'call_id',
      label: 'Linked Call',
      sortable: true,
      className: 'font-mono text-slate-300',
      render: (cid) => (cid && cid > 0 ? `#${cid}` : <span className="text-slate-600 italic">Unlinked</span>),
    },
    {
      key: 'event_type',
      label: 'Event Type',
      sortable: true,
      render: (type) => <StatusBadge status={type} />,
    },
    {
      key: 'processed',
      label: 'Processing Status',
      sortable: true,
      render: (processed, row) => (
        <div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-mono font-semibold uppercase ${
              processed
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}
          >
            {processed ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
            {processed ? 'PROCESSED' : 'DISCARDED'}
          </span>
          {row.discard_reason && (
            <p className="mt-1 text-[10px] text-slate-400 max-w-xs truncate">{row.discard_reason}</p>
          )}
        </div>
      ),
    },
    {
      key: 'received_at',
      label: 'Timestamp (UTC)',
      sortable: true,
      className: 'font-mono text-xs text-slate-400',
      render: (ts) => (ts ? new Date(ts).toLocaleTimeString() : '—'),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Radio className="h-5 w-5 text-rose-400" />
            Telecom Provider Webhook Ingestion
          </h2>
          <p className="text-xs text-slate-400">
            Real-time webhook listener with idempotency verification and state machine out-of-order rejection.
          </p>
        </div>
      </div>

      {/* Simulator Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Form Card (2 cols) */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl lg:col-span-2">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h3 className="text-base font-bold text-white">Carrier Webhook Event Simulator</h3>
              <p className="text-xs text-slate-400">Simulate incoming carrier event callbacks (POST /events/provider-webhook)</p>
            </div>
            <button
              type="button"
              onClick={generateRandomEventId}
              className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-mono"
            >
              <Sparkles className="h-3.5 w-3.5" />
              New Event ID
            </button>
          </div>

          <form onSubmit={handleSendWebhook} className="mt-5 space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Unique Event ID (Idempotency Key)
                </label>
                <input
                  type="text"
                  required
                  value={eventId}
                  onChange={(e) => setEventId(e.target.value)}
                  placeholder="e.g. EVT-9FA2B1"
                  className="w-full rounded-lg border border-slate-800 bg-[#0B0F17] px-3.5 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
                />
                <p className="mt-1 text-[10px] text-slate-500">
                  Submitting the same ID twice tests the deduplication log.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Provider Call ID
                </label>
                <input
                  type="text"
                  required
                  value={providerCallId}
                  onChange={(e) => setProviderCallId(e.target.value)}
                  placeholder="e.g. PA-5D2B1C90 หรือ PB-44AF10"
                  className="w-full rounded-lg border border-slate-800 bg-[#0B0F17] px-3.5 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
                />
                <p className="mt-1 text-[10px] text-slate-500">
                  Carrier reference returned during call initiation.
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                Event State Type
              </label>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                {['RINGING', 'ANSWERED', 'CONNECTED', 'COMPLETED', 'FAILED', 'TIMEOUT'].map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setEventType(type)}
                    className={`rounded-lg border px-3 py-2 text-xs font-mono font-semibold transition-all ${
                      eventType === type
                        ? 'border-indigo-500 bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : 'border-slate-800 bg-[#0B0F17] text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 disabled:opacity-50 transition-all"
            >
              <Send className={`h-4 w-4 ${submitting ? 'animate-spin' : ''}`} />
              {submitting ? 'Delivering Webhook...' : 'Deliver Webhook Event'}
            </button>
          </form>
        </div>

        {/* Webhook Response & Idempotency Notes (1 col) */}
        <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 shadow-xl flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
              <ShieldCheck className="h-4 w-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-white">Event Engine Rules</h3>
            </div>

            <div className="mt-3 space-y-3 text-xs text-slate-400">
              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3">
                <span className="font-semibold text-slate-200">1. Idempotency</span>
                <p className="mt-1 text-[11px]">
                  Duplicate <code>event_id</code> is silently ignored to prevent corrupted call states from chaotic network retries.
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3">
                <span className="font-semibold text-slate-200">2. Out-of-Order Safety</span>
                <p className="mt-1 text-[11px]">
                  Transitions like <code>COMPLETED</code> before <code>RINGING</code> are rejected without changing the call state.
                </p>
              </div>
            </div>
          </div>

          {webhookResponse && (
            <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3.5 space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-slate-300">
                <span className="font-bold uppercase">Result:</span>
                <span className={webhookResponse.processed ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                  {webhookResponse.processed ? 'SUCCESS' : 'DISCARDED'}
                </span>
              </div>
              <div className="text-slate-400 text-[11px]">
                <strong>Reason:</strong> {webhookResponse.reason}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Historical Webhook Events Log */}
      <DataTable
        columns={columns}
        data={events}
        loading={loading}
        searchPlaceholder="Search event log by event ID or call ID..."
        emptyTitle="No webhook events recorded"
        emptyMessage="Incoming carrier events will be logged and displayed here."
      />
    </div>
  );
}
