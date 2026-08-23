import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Toast from './components/Toast';

// Pages
import Dashboard from './pages/Dashboard';
import Borrowers from './pages/Borrowers';
import Calls from './pages/Calls';
import CallStats from './pages/CallStats';
import Dialer from './pages/Dialer';
import Events from './pages/Events';
import Predictive from './pages/Predictive';
import Agents from './pages/Agents';

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const showToast = ({ type = 'info', message, duration = 4000 }) => {
    setToast({
      id: Date.now(),
      type,
      message,
      duration,
    });
  };

  const handleManualRefresh = () => {
    setRefreshing(true);
    setRefreshKey((k) => k + 1);
    setTimeout(() => setRefreshing(false), 600);
  };

  const pageMeta = {
    dashboard: {
      title: 'Operations Dashboard',
      subtitle: 'Real-time campaign overview, agent capacity & active call stream',
    },
    borrowers: {
      title: 'Borrower Queue',
      subtitle: 'Manage debt collection contact list & call allocation status',
    },
    calls: {
      title: 'Call Sessions Audit',
      subtitle: 'Real-time log of initiated, ringing, connected & completed calls',
    },
    'call-stats': {
      title: 'Performance & Statistics',
      subtitle: 'Answer rate metrics, pipeline efficiency & carrier completion',
    },
    dialer: {
      title: 'Dialer Control Center',
      subtitle: 'Trigger progressive dialing cycles and query predictive pacing',
    },
    events: {
      title: 'Events & Webhooks',
      subtitle: 'Idempotency verification & carrier event state transitions',
    },
    predictive: {
      title: 'Predictive Pacing Engine',
      subtitle: 'Mathematical pipeline estimation & Safety Controller approvals',
    },
    agents: {
      title: 'Agent Workforce Pool',
      subtitle: 'Manage agent availability, pauses, and lifecycle transitions',
    },
  };

  const currentMeta = pageMeta[activePage] || pageMeta.dashboard;

  const renderActivePage = () => {
    const props = {
      key: refreshKey,
      onNavigate: setActivePage,
      showToast,
    };

    switch (activePage) {
      case 'dashboard':
        return <Dashboard {...props} />;
      case 'borrowers':
        return <Borrowers {...props} />;
      case 'calls':
        return <Calls {...props} />;
      case 'call-stats':
        return <CallStats {...props} />;
      case 'dialer':
        return <Dialer {...props} />;
      case 'events':
        return <Events {...props} />;
      case 'predictive':
        return <Predictive {...props} />;
      case 'agents':
        return <Agents {...props} />;
      default:
        return <Dashboard {...props} />;
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B0F17] font-sans text-slate-100 antialiased selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Fixed Navigation Sidebar */}
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header */}
        <Header
          title={currentMeta.title}
          subtitle={currentMeta.subtitle}
          onRefresh={handleManualRefresh}
          refreshing={refreshing}
          onToggleSidebar={() => setMobileSidebarOpen((o) => !o)}
        />

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
          <div className="mx-auto max-w-7xl">
            {renderActivePage()}
          </div>
        </main>
      </div>

      {/* Floating Global Toast Notification */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
