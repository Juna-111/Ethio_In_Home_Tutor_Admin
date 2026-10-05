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
    const target = parseStartParam(
      webApp?.initDataUnsafe?.start_param || new URLSearchParams(window.location.search).get('start')
    );
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

  const homeCards = [
    {
      id: 'requests',
      title: 'Match & Assign',
      description: 'Review parent requests, find suitable tutors, and manage assignments.',
      icon: ClipboardList,
      tone: 'coral',
      badge: dashboard?.pending_requests || 0,
      badgeLabel: 'pending',
    },
    {
      id: 'tutors',
      title: 'Tutor Management',
      description: 'Review tutor profiles, verification, credentials, and availability.',
      icon: GraduationCap,
      tone: 'citrus',
      badge: dashboard?.pending_tutors || 0,
      badgeLabel: 'to verify',
    },
    {
      id: 'crm',
      title: 'Parents & Families',
      description: 'View customer activity, requests, and family records in one place.',
      icon: Contact,
      tone: 'green',
    },
    {
      id: 'pipeline',
      title: 'Assignment Pipeline',
      description: 'Track every request from matching through active tutoring.',
      icon: GitPullRequest,
      tone: 'blue',
    },
    {
      id: 'ops',
      title: 'Needs Review',
      description: 'Handle operational exceptions and items that need admin attention.',
      icon: ShieldAlert,
      tone: 'coral',
    },
    {
      id: 'analytics',
      title: 'Insights',
      description: 'Understand demand, tutor supply, conversion, and platform performance.',
      icon: BarChart3,
      tone: 'blue',
    },
    {
      id: 'coverage',
      title: 'Coverage',
      description: 'See where tutor supply is strong, weak, or currently idle.',
      icon: UsersRound,
      tone: 'green',
    },
    {
      id: 'export',
      title: 'Export Center',
      description: 'Download operational data for reporting and administration.',
      icon: Download,
      tone: 'citrus',
    },
  ];

  if (dashboard?.admin_role === 'super_admin') {
    homeCards.push({
      id: 'admins',
      title: 'Admin Settings',
      description: 'Manage administrator access and platform administration controls.',
      icon: Settings,
      tone: 'pine',
    });
  }

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    const backButton = tg?.BackButton;
    if (!backButton) return undefined;
    if (activeSection !== 'overview' && view.status === 'ready') {
      backButton.show();
      const handleBack = () => setActiveSection('overview');
      backButton.onClick(handleBack);
      return () => {
        backButton.offClick(handleBack);
        backButton.hide();
      };
    }
    backButton.hide();
    return undefined;
  }, [activeSection, view.status]);

  return (
    <div className="admin-app">
      <header className="admin-topbar">
        <a className="admin-brand" href="/admin.html" aria-label="Ethio In-Home Tutor Admin home">
          <span className="brand-mark" aria-hidden="true"><span>E</span></span>
          <span className="brand-copy"><strong>Ethio In-Home Tutor</strong><span className="brand-admin">ADMIN CONSOLE</span></span>
        </a>
        <div className="topbar-status"><span className="status-dot" />
          {dashboard
            ? `SIGNED IN · ${(dashboard.admin_role || 'ADMIN').toUpperCase()}${dashboard.admin_telegram_id ? ` · ${dashboard.admin_telegram_id}` : ''}`
            : 'ADMIN OPERATIONS'}
        </div>
      </header>

      <main className="admin-main">
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
                  {metrics.slice(0, 4).map(({ label, value, icon: Icon, tone }, index) => (
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

                <section className="admin-home-section" aria-labelledby="admin-tools-title">
                  <div className="section-title-row admin-home-title">
                    <div>
                      <p className="eyebrow">ETHIO IN-HOME TUTOR · ADMIN</p>
                      <h2 id="admin-tools-title">What do you want to manage?</h2>
                      <p>Everything is grouped by purpose. Choose a workspace to get started.</p>
                    </div>
                    <span className="queue-total">
                      {formatCount((dashboard?.pending_tutors || 0) + (dashboard?.pending_requests || 0))} NEED ATTENTION
                    </span>
                  </div>

                  <div className="admin-home-grid">
                    {homeCards.map(({ id, title, description, icon: Icon, tone, badge, badgeLabel }) => (
                      <button
                        key={id}
                        type="button"
                        className={`admin-home-card admin-home-card-${tone}`}
                        onClick={() => setActiveSection(id)}
                      >
                        <span className="admin-home-card-icon"><Icon size={21} strokeWidth={1.8} /></span>
                        <span className="admin-home-card-copy">
                          <strong>{title}</strong>
                          <small>{description}</small>
                        </span>
                        <span className="admin-home-card-arrow" aria-hidden="true"><ArrowUpRight size={17} /></span>
                        {badge ? <span className="admin-home-card-badge">{formatCount(badge)} {badgeLabel}</span> : null}
                      </button>
                    ))}
                  </div>
                </section>
              </>
            )}

            {view.status === 'ready' && activeSection !== 'overview' && (
              <div className="admin-section-toolbar">
                <button type="button" className="admin-home-back" onClick={() => setActiveSection('overview')}>
                  <LayoutDashboard size={15} />
                  <span>Admin Home</span>
                </button>
                <span className="admin-section-context">ETHIO IN-HOME TUTOR / ADMIN WORKSPACE</span>
              </div>
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
                <span>ETHIO IN-HOME TUTOR <i>·</i> ADMIN OPERATIONS</span>
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
