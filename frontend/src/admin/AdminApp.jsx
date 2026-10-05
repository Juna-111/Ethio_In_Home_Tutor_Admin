import { useEffect, useState } from 'react';
import { AlertTriangle, LayoutDashboard, RefreshCw, ShieldCheck } from 'lucide-react';
import { getAdminDashboard } from '../services/api';
import AdminControlCenter from './AdminControlCenter.jsx';
import CoverageBoard from './CoverageBoard.jsx';
import IdleTutors from './IdleTutors.jsx';
import RequestWorkbench from './RequestWorkbench.jsx';
import TutorList from './TutorList.jsx';
import TutorVerificationModal from './TutorVerificationModal.jsx';
import OpsQueue from './OpsQueue.jsx';
import AnalyticsBoard from './AnalyticsBoard.jsx';
import ExportCenter from './ExportCenter.jsx';
import AdminManagement from './AdminManagement.jsx';
import CustomerCRM from './CustomerCRM.jsx';
import AssignmentPipeline from './AssignmentPipeline.jsx';

function parseStartParam(value) {
  const match = /^(tutor|request)_(\d+)$/.exec(value || '');
  return match ? { type: match[1], id: Number(match[2]) } : null;
}

export default function AdminApp() {
  const [dashboard, setDashboard] = useState(null);
  const [view, setView] = useState({ status: 'loading', message: '' });
  const [startTarget, setStartTarget] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeSection, setActiveSection] = useState('overview');
  const [selectedTutorId, setSelectedTutorId] = useState(null);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready(); tg?.expand();
    const target = parseStartParam(tg?.initDataUnsafe?.start_param || new URLSearchParams(window.location.search).get('start'));
    setStartTarget(target);
    if (target?.type === 'request') setActiveSection('requests');
    if (target?.type === 'tutor') { setActiveSection('tutors'); setSelectedTutorId(target.id); }
    let active = true;
    getAdminDashboard().then((result) => {
      if (active) { setDashboard(result); setView({ status: 'ready', message: '' }); }
    }).catch((error) => {
      if (!active) return;
      setView(error.status === 401 || error.status === 403 ? { status: 'unauthorized', message: '' } : { status: 'error', message: error.message || 'Dashboard could not be loaded.' });
    });
    return () => { active = false; };
  }, [refreshKey]);

  useEffect(() => {
    const back = window.Telegram?.WebApp?.BackButton;
    if (!back) return undefined;
    if (activeSection !== 'overview' && view.status === 'ready') {
      back.show();
      const handler = () => setActiveSection('overview');
      back.onClick(handler);
      return () => { back.offClick(handler); back.hide(); };
    }
    back.hide();
    return undefined;
  }, [activeSection, view.status]);

  const navigate = (section, id) => {
    setActiveSection(section);
    if (section === 'tutors' && id) setSelectedTutorId(id);
  };

  return (
    <div className="admin-app">
      <header className="admin-topbar">
        <a className="admin-brand" href="/admin.html" aria-label="Ethio In-Home Tutor Admin home">
          <span className="brand-mark" aria-hidden="true"><span>E</span></span>
          <span className="brand-copy"><strong>Ethio In-Home Tutor</strong><span className="brand-admin">ADMIN CONSOLE</span></span>
        </a>
        <div className="topbar-status"><span className="status-dot" />{dashboard ? 'SIGNED IN · ' + (dashboard.admin_role || 'ADMIN').toUpperCase() : 'ADMIN OPERATIONS'}</div>
      </header>
      <main className="admin-main">
        {view.status === 'unauthorized' ? (
          <section className="access-state" role="status"><div className="access-icon"><ShieldCheck size={23} /></div><p className="eyebrow">RESTRICTED AREA</p><h2>Admin access required</h2><p>Open this app from Telegram with an active administrator account.</p></section>
        ) : view.status === 'error' ? (
          <section className="access-state error-state" role="alert"><div className="access-icon"><AlertTriangle size={23} /></div><p className="eyebrow">CONNECTION ISSUE</p><h2>Dashboard unavailable</h2><p>{view.message}</p><button className="retry-button" type="button" onClick={() => setRefreshKey((k) => k + 1)}>Try again</button></section>
        ) : (
          <>
            {activeSection === 'overview' && <AdminControlCenter onNavigate={navigate} />}
            {activeSection !== 'overview' && <div className="admin-section-toolbar"><button type="button" className="admin-home-back" onClick={() => setActiveSection('overview')}><LayoutDashboard size={15} /><span>Control Center</span></button><span className="admin-section-context">ETHIO IN-HOME TUTOR / ADMIN</span><button type="button" className="refresh-button" onClick={() => setRefreshKey((k) => k + 1)} aria-label="Refresh admin data"><RefreshCw size={16} /></button></div>}
            {view.status === 'ready' && activeSection === 'requests' && <RequestWorkbench initialRequestId={startTarget?.type === 'request' ? startTarget.id : null} />}
            {view.status === 'ready' && activeSection === 'tutors' && <TutorList onSelectTutor={(id) => setSelectedTutorId(id)} />}
            {view.status === 'ready' && activeSection === 'crm' && <CustomerCRM />}
            {view.status === 'ready' && activeSection === 'pipeline' && <AssignmentPipeline />}
            {view.status === 'ready' && activeSection === 'ops' && <OpsQueue onSelectTutor={(id) => setSelectedTutorId(id)} />}
            {view.status === 'ready' && activeSection === 'analytics' && <AnalyticsBoard />}
            {view.status === 'ready' && activeSection === 'coverage' && <><CoverageBoard /><div style={{ marginTop: 30 }}><IdleTutors /></div></>}
            {view.status === 'ready' && activeSection === 'export' && <ExportCenter />}
            {view.status === 'ready' && activeSection === 'admins' && dashboard?.admin_role === 'super_admin' && <AdminManagement />}
            {view.status === 'ready' && activeSection !== 'overview' && <footer className="admin-footer"><span><span className="status-dot" /> LIVE DATA CONNECTED</span><span>ETHIO IN-HOME TUTOR <i>·</i> ADMIN OPERATIONS</span></footer>}
          </>
        )}
      </main>
      {selectedTutorId && <TutorVerificationModal tutorId={selectedTutorId} onClose={() => setSelectedTutorId(null)} onUpdated={() => setRefreshKey((k) => k + 1)} />}
    </div>
  );
}
