import { useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowUpRight, BarChart3, ClipboardList,
  GraduationCap, LayoutDashboard, RefreshCw, ShieldCheck, UsersRound,
  ShieldAlert, Download, Settings, GitPullRequest, Contact
} from 'lucide-react';
import { getAdminDashboard } from '../services/api';
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

function formatCount(value) {
  return new Intl.NumberFormat().format(value || 0);
}

export default function AdminApp() {
  const [dashboard, setDashboard] = useState(null);
  const [view, setView] = useState({ status: 'loading', message: '' });
  const [startTarget, setStartTarget] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeSection, setActiveSection] = useState('overview');
  const [selectedTutorId, setSelectedTutorId] = useState(null);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
    const target = parseStartParam(webApp?.initDataUnsafe?.start_param);
    setStartTarget(target);
    if (target?.type === 'request') setActiveSection('requests');
    if (target?.type === 'tutor') {
      setActiveSection('tutors');
      setSelectedTutorId(target.id);
    }

    let active = true;
    getAdminDashboard()
      .then((result) => {
        if (!active) return;
        setDashboard(result);
        setView({ status: 'ready', message: '' });
      })
      .catch((error) => {
        if (!active) return;
        if (error.status === 401 || error.status === 403) {
          setView({ status: 'unauthorized', message: '' });
        } else {
          setView({ status: 'error', message: error.message || 'Dashboard could not be loaded.' });
        }
      });

    return () => {
      active = false;
    };
  }, [refreshKey]);

  const metrics = dashboard ? [
    { label: 'Pending tutors', value: dashboard.pending_tutors, icon: GraduationCap, tone: 'citrus' },
    { label: 'Pending requests', value: dashboard.pending_requests, icon: ClipboardList, tone: 'coral' },
    { label: 'Active assignments', value: dashboard.active_assignments, icon: Activity, tone: 'green' },
    { label: 'Requests today', value: dashboard.requests_today, icon: ArrowUpRight, tone: 'blue' },
    { label: 'Conversion rate', value: `${dashboard.conversion_rate_pct ?? 0}%`, icon: ShieldCheck, tone: 'green' },
    { label: 'Avg days to assign', value: `${dashboard.avg_days_to_assign ?? 0}d`, icon: Activity, tone: 'citrus' },
    { label: 'Tutor funnel conv.', value: `${dashboard.tutor_verification_funnel_pct ?? 0}%`, icon: ArrowUpRight, tone: 'blue' },
  ] : [];

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'requests', label: 'Requests', icon: ClipboardList },
    { id: 'tutors', label: 'Tutors', icon: GraduationCap },
    { id: 'crm', label: 'Parent CRM', icon: Contact },
    { id: 'pipeline', label: 'Pipeline', icon: GitPullRequest },
    { id: 'ops', label: 'Ops Queue', icon: ShieldAlert },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'coverage', label: 'Coverage', icon: UsersRound },
    { id: 'export', label: 'Export', icon: Download },
    ...(dashboard?.admin_role === 'super_admin' ? [
      { id: 'admins', label: 'Settings', icon: Settings }
    ] : []),
  ];

  return (
    <div className="admin-app">
      <header className="admin-topbar">
        <a className="admin-brand" href="/admin.html" aria-label="MentorLink Admin home">
          <span className="brand-mark"><span /></span>
          <span>mentorlink<span className="brand-admin"> / admin</span></span>
        </a>
        <div className="topbar-status"><span className="status-dot" />
          {dashboard
            ? `SIGNED IN · ${(dashboard.admin_role || 'ADMIN').toUpperCase()}${dashboard.admin_telegram_id ? ` · ${dashboard.admin_telegram_id}` : ''}`
            : 'OPERATIONS'}
        </div>
      </header>

      <main className="admin-main">
        {view.status === 'ready' && (
          <nav className="admin-nav" aria-label="Admin sections" role="tablist">
            {navItems.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={activeSection === id}
                className={activeSection === id ? 'admin-nav-item active' : 'admin-nav-item'}
                onClick={() => setActiveSection(id)}
              ><Icon size={16} /><span>{label}</span></button>
            ))}
          </nav>
        )}

        {activeSection === 'overview' && (
          <div className="page-heading">
            <div>
              <p className="eyebrow">ADMINISTRATION <span> / </span> OVERVIEW</p>
              <h1>Operations overview</h1>
              <p className="heading-copy">A live read on tutor supply, quality verification, and active demand.</p>
            </div>
            <button
              className="refresh-button"
              type="button"
              onClick={() => {
                setView({ status: 'loading', message: '' });
                setRefreshKey((key) => key + 1);
              }}
              disabled={view.status === 'loading'}
              aria-label="Refresh dashboard"
              title="Refresh dashboard"
            >
              <RefreshCw size={17} className={view.status === 'loading' ? 'spin' : ''} />
            </button>
          </div>
        )}

        {view.status === 'unauthorized' ? (
          <section className="access-state" role="status">
            <div className="access-icon"><ShieldCheck size={23} /></div>
            <p className="eyebrow">RESTRICTED AREA</p>
            <h2>Admin access required</h2>
            <p>Open this app from Telegram with an active administrator account.</p>
            <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center' }}>
              <a href="/index.html?tab=tutor_portal" className="primary-button" style={{ textDecoration: 'none' }}>
                Go to Tutor Portal (My Teaching)
              </a>
              <a href="/index.html?tab=parent_portal" className="quiet-button" style={{ textDecoration: 'none' }}>
                Go to Parent Portal (My Requests)
              </a>
            </div>
          </section>
        ) : view.status === 'error' ? (
          <section className="access-state error-state" role="alert">
            <div className="access-icon"><AlertTriangle size={23} /></div>
            <p className="eyebrow">CONNECTION ISSUE</p>
            <h2>Dashboard unavailable</h2>
            <p>{view.message}</p>
            <button className="retry-button" type="button" onClick={() => setRefreshKey((key) => key + 1)}>
              Try again
            </button>
          </section>
        ) : (
          <>
            {view.status === 'loading' && activeSection === 'overview' ? (
              <div className="metrics-grid" aria-label="Loading dashboard metrics">
                {Array.from({ length: 4 }, (_, index) => <div className="metric-skeleton" key={index} />)}
              </div>
            ) : null}

            {view.status === 'ready' && activeSection === 'overview' && (
              <>
                <section className="metrics-grid" aria-label="Platform metrics">
                  {metrics.map(({ label, value, icon: Icon, tone }, index) => (
                    <article className={`metric metric-${tone}`} key={label} style={{ '--stagger': `${index * 70}ms` }}>
                      <div className="metric-topline">
                        <span>{label}</span>
                        <Icon size={18} strokeWidth={1.8} />
                      </div>
                      <strong>{typeof value === 'number' ? formatCount(value) : value}</strong>
                      <span className="metric-rule" />
                    </article>
                  ))}
                </section>
                <section className="queue-section">
                  <div className="section-title-row">
                    <div>
                      <p className="eyebrow">WORK QUEUE</p>
                      <h2>Needs attention</h2>
                    </div>
                    <span className="queue-total">
                      {formatCount((dashboard?.pending_tutors || 0) + (dashboard?.pending_requests || 0))} OPEN
                    </span>
                  </div>
                  <div className="queue-list">
                    <div className="queue-item clickable" onClick={() => setActiveSection('tutors')}>
                      <span className="queue-icon queue-icon-coral"><GraduationCap size={18} /></span>
                      <span className="queue-label"><strong>Tutor verification</strong><small>Profiles awaiting checklist review</small></span>
                      <strong className="queue-count">{formatCount(dashboard.pending_tutors)}</strong>
                    </div>
                    <div className="queue-item clickable" onClick={() => setActiveSection('requests')}>
                      <span className="queue-icon queue-icon-green"><ClipboardList size={18} /></span>
                      <span className="queue-label"><strong>Parent requests</strong><small>Students waiting for workbench matching</small></span>
                      <strong className="queue-count">{formatCount(dashboard.pending_requests)}</strong>
                    </div>
                  </div>
                </section>
              </>
            )}

            {view.status === 'ready' && activeSection === 'requests' && (
              <RequestWorkbench initialRequestId={startTarget?.type === 'request' ? startTarget.id : null} />
            )}
            {view.status === 'ready' && activeSection === 'tutors' && (
              <TutorList onSelectTutor={(id) => setSelectedTutorId(id)} />
            )}
            {view.status === 'ready' && activeSection === 'crm' && (
              <CustomerCRM />
            )}
            {view.status === 'ready' && activeSection === 'pipeline' && (
              <AssignmentPipeline />
            )}
            {view.status === 'ready' && activeSection === 'ops' && (
              <OpsQueue onSelectTutor={(id) => setSelectedTutorId(id)} />
            )}
            {view.status === 'ready' && activeSection === 'analytics' && <AnalyticsBoard />}
            {view.status === 'ready' && activeSection === 'coverage' && (
              <>
                <CoverageBoard />
                <div style={{ marginTop: '30px' }}><IdleTutors /></div>
              </>
            )}
            {view.status === 'ready' && activeSection === 'export' && <ExportCenter />}
            {view.status === 'ready' && activeSection === 'admins' && <AdminManagement />}

            {view.status === 'ready' && (
              <footer className="admin-footer">
                <span><span className="status-dot" /> LIVE DATA CONNECTED</span>
                <span>MENTORLINK ADMIN <i>·</i> PHASE 5 (FULL CAPABILITIES)</span>
              </footer>
            )}
          </>
        )}
      </main>

      {selectedTutorId && (
        <TutorVerificationModal
          tutorId={selectedTutorId}
          onClose={() => setSelectedTutorId(null)}
          onUpdated={() => setRefreshKey((k) => k + 1)}
        />
      )}
    </div>
  );
}
