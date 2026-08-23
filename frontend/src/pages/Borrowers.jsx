import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Phone, Search, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react';
import api from '../services/api';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';

export default function Borrowers({ showToast }) {
  const [borrowers, setBorrowers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form inputs
  const [name, setName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [formError, setFormError] = useState('');

  const fetchBorrowers = async () => {
    try {
      setLoading(true);
      const data = await api.getBorrowers();
      setBorrowers(data);
    } catch (err) {
      showToast?.({
        type: 'error',
        message: 'Failed to fetch borrowers: ' + err.message,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBorrowers();
  }, []);

  const handleCreateBorrower = async (e) => {
    e.preventDefault();
    if (!name.trim() || !phoneNumber.trim()) {
      setFormError('Please enter both name and phone number.');
      return;
    }

    try {
      setSubmitting(true);
      setFormError('');
      const newBorrower = await api.createBorrower(name.trim(), phoneNumber.trim());
      showToast?.({
        type: 'success',
        message: `Borrower ${newBorrower.name} (${newBorrower.phone_number}) created successfully!`,
      });
      setName('');
      setPhoneNumber('');
      setIsModalOpen(false);
      await fetchBorrowers();
    } catch (err) {
      setFormError(err.message);
      showToast?.({
        type: 'error',
        message: 'Error creating borrower: ' + err.message,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      key: 'id',
      label: 'ID',
      sortable: true,
      className: 'font-mono text-slate-400 w-16',
      render: (id) => `#${id}`,
    },
    {
      key: 'name',
      label: 'Borrower Name',
      sortable: true,
      className: 'font-semibold text-white',
      render: (name, b) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-800 text-indigo-400 font-semibold text-xs border border-slate-700">
            {name.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="font-medium text-slate-200">{name}</div>
            <div className="text-[11px] text-slate-500 font-mono">ID: {b.id}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'phone_number',
      label: 'Phone Number',
      sortable: true,
      className: 'font-mono text-slate-300',
      render: (phone) => (
        <div className="flex items-center gap-1.5 text-slate-300 font-mono">
          <Phone className="h-3.5 w-3.5 text-slate-500" />
          {phone}
        </div>
      ),
    },
    {
      key: 'state',
      label: 'Queue Status',
      sortable: true,
      render: (state) => <StatusBadge status={state} />,
    },
  ];

  // Quick stats
  const pendingCount = borrowers.filter((b) => b.state === 'PENDING').length;
  const inCallCount = borrowers.filter((b) => b.state === 'IN_CALL' || b.state === 'RESERVED').length;
  const completedCount = borrowers.filter((b) => b.state === 'COMPLETED').length;

  return (
    <div className="space-y-6">
      {/* Page Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="h-5 w-5 text-indigo-400" />
            Borrower Campaign Queue
          </h2>
          <p className="text-xs text-slate-400">
            Contacts eligible for outbound progressive and predictive dialing allocation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-all"
          >
            <UserPlus className="h-4 w-4" />
            Create Borrower
          </button>
        </div>
      </div>

      {/* Summary Mini Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-[#111827] p-4">
          <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Pending Contacts</span>
          <div className="mt-1 text-2xl font-bold text-sky-400 font-mono">{pendingCount}</div>
          <p className="text-[11px] text-slate-500 mt-0.5">Ready to be dialed in next cycle</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-[#111827] p-4">
          <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">In-Flight / Reserved</span>
          <div className="mt-1 text-2xl font-bold text-cyan-400 font-mono">{inCallCount}</div>
          <p className="text-[11px] text-slate-500 mt-0.5">Currently assigned to an agent call</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-[#111827] p-4">
          <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Completed Contacts</span>
          <div className="mt-1 text-2xl font-bold text-emerald-400 font-mono">{completedCount}</div>
          <p className="text-[11px] text-slate-500 mt-0.5">Successfully contacted</p>
        </div>
      </div>

      {/* Borrowers Data Table */}
      <DataTable
        columns={columns}
        data={borrowers}
        loading={loading}
        searchPlaceholder="Search borrowers by name or phone..."
        emptyTitle="No borrowers found"
        emptyMessage="Add contacts to the campaign list to allow the dialer to allocate outbound calls."
        emptyAction={
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
          >
            <UserPlus className="h-3.5 w-3.5" />
            Add Borrower
          </button>
        }
      />

      {/* Create Borrower Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setFormError('');
        }}
        title="Add New Borrower"
      >
        <form onSubmit={handleCreateBorrower} className="space-y-4">
          {formError && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 shrink-0" />
              {formError}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Borrower Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full rounded-lg border border-slate-800 bg-[#0B0F17] px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Phone Number
            </label>
            <input
              type="text"
              required
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="e.g. 5551234567"
              className="w-full rounded-lg border border-slate-800 bg-[#0B0F17] px-3.5 py-2.5 text-sm font-mono text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <p className="mt-1 text-[11px] text-slate-500">
              Unique phone number dialed by Telecom Provider A or B.
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
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Save Borrower'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
