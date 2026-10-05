import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, GraduationCap, Search, Sparkles, X } from 'lucide-react';
import { getAdminControlCenter, getAdminDashboard, getAdminRequest, getAdminTutors } from '../services/api';
import './admin-control.css';

const age = (hours) => {
  if (hours == null) return '';
  if (hours < 1) return 'just now';
  if (hours < 24) return Math.round(hours) + 'h';
  return Math.floor(hours / 24) + 'd';
};

export default function AdminControlCenter({ onNavigate }) {
  const [data, setData] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);

  const load = () => {
    setState('loading');
    setError('');
    Promise.all([getAdminControlCenter(), getAdminDashboard()])
      .then(([result, overview]) => { setData(result); setDashboard(overview); setState('ready'); })
      .catch((err) => { setError(err.message || 'Control center unavailable.'); setState('error'); });
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const q = query.trim();
    if (!q) { setResults(null); return undefined; }
    const timer = setTimeout(async () => {
      try {
        const [tutors, request] = await Promise.all([
          getAdminTutors({ search: q, page: 1, page_size: 5 }),
          /^\d+$/.test(q) ? getAdminRequest(Number(q)).catch(() => null) : Promise.resolve(null),
        ]);
        setResults({ tutors: tutors.items || [], request });
      } catch (_) {
        setResults({ tutors: [], request: null });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  const attention = data?.attention || [];
  const urgent = useMemo(
    () => attention.filter((item) => item.severity === 'critical' || item.severity === 'high'),
    [attention],
  );

  if (state === 'loading') {
    return <div className="control-loading" aria-label="Loading operations"><span /><span /><span /></div>;
  }

  if (state === 'error') {
    return (
      <section className="control-error" role="alert">
        <AlertTriangle size={19} />
        <div><strong>Could not load operations</strong><p>{error}</p></div>
        <button type="button" onClick={load}>Try again</button>
      </section>
    );
  }

  return (
    <section className="control-center">
      <header className="control-heading">
        <div>
          <p className="eyebrow">ETHIO IN-HOME TUTOR · ADMIN</p>
          <h1>{urgent.length ? `${urgent.length} thing${urgent.length === 1 ? '' : 's'} need your attention.` : 'Everything is under control.'}</h1>
          <p>{urgent.length ? 'The platform has already done the routine work. Here is what still needs a human decision.' : 'No urgent decision is waiting. The platform is monitoring matching, verification and assignments.'}</p>
        </div>
        <div className="control-mark"><span className="status-dot" /> LIVE</div>
      </header>

      <div className="control-search">
        <Search size={17} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a request or tutor" aria-label="Find a request or tutor" />
        {query && <button type="button" aria-label="Clear search" onClick={() => setQuery('')}><X size={14} /></button>}
      </div>

      {dashboard && (
        <div className="control-pulse" aria-label="Platform pulse">
          <button type="button" onClick={() => onNavigate('requests')}><strong>{dashboard.pending_requests || 0}</strong><span>requests waiting</span></button>
          <button type="button" onClick={() => onNavigate('tutors')}><strong>{dashboard.pending_tutors || 0}</strong><span>tutors to verify</span></button>
          <button type="button" onClick={() => onNavigate('pipeline')}><strong>{dashboard.active_assignments || 0}</strong><span>active assignments</span></button>
          <button type="button" onClick={() => onNavigate('analytics')}><strong>{dashboard.conversion_rate_pct ?? 0}%</strong><span>request conversion</span></button>
        </div>
      )}

      <div className="control-workspaces" aria-label="Admin workspaces">
        <span>WORKSPACES</span>
        <button type="button" onClick={() => onNavigate('requests')}>Matching</button>
        <button type="button" onClick={() => onNavigate('tutors')}>Tutors</button>
        <button type="button" onClick={() => onNavigate('crm')}>Families</button>
        <button type="button" onClick={() => onNavigate('pipeline')}>Assignments</button>
        <button type="button" onClick={() => onNavigate('ops')}>Incidents</button>
        <button type="button" onClick={() => onNavigate('analytics')}>Insights</button>
        <button type="button" onClick={() => onNavigate('coverage')}>Coverage</button>
        <button type="button" onClick={() => onNavigate('export')}>Exports</button>
        {dashboard?.admin_role === 'super_admin' && <button type="button" onClick={() => onNavigate('admins')}>Admin access</button>}
      </div>

      {results && (
        <div className="control-search-results">
          {results.request && (
            <button type="button" onClick={() => { setQuery(''); onNavigate('requests', results.request.id); }}>
              <span><strong>Request #{results.request.id}</strong><small>{results.request.parent_name} · {results.request.location_subcity}</small></span><ArrowRight size={15} />
            </button>
          )}
          {results.tutors.map((tutor) => (
            <button key={tutor.id} type="button" onClick={() => { setQuery(''); onNavigate('tutors', tutor.id); }}>
              <span><strong>{tutor.full_name}</strong><small>{tutor.base_subcity} · {tutor.status}</small></span><ArrowRight size={15} />
            </button>
          ))}
          {!results.request && !results.tutors.length && <div className="control-search-empty">Nothing found.</div>}
        </div>
      )}

      {attention.length ? (
        <div className="decision-list">
          {attention.map((item, index) => (
            <Decision key={item.id} item={item} first={index === 0} onNavigate={onNavigate} />
          ))}
        </div>
      ) : (
        <div className="clear-state">
          <div className="clear-icon"><CheckCircle2 size={24} /></div>
          <div><strong>No human action required.</strong><span>Matching, verification and assignments are being handled by the platform.</span></div>
        </div>
      )}

      <footer className="control-footer">
        <div><Sparkles size={14} /><span>{data.next_move}</span></div>
        <span className="control-health">{data.active_assignments || 0} active tutoring · {data.pending_requests || 0} waiting</span>
      </footer>
    </section>
  );
}

function Decision({ item, first, onNavigate }) {
  const urgent = item.severity === 'critical' || item.severity === 'high';
  return (
    <article className={`decision ${urgent ? 'decision-urgent' : ''} ${first ? 'decision-first' : ''}`}>
      <div className="decision-icon">{urgent ? <AlertTriangle size={17} /> : item.kind === 'verification' ? <GraduationCap size={17} /> : <Clock3 size={17} />}</div>
      <div className="decision-body">
        <div className="decision-top">
          <strong>{item.title}</strong>
          {item.age_hours != null && <span>{age(item.age_hours)}</span>}
        </div>
        <p>{item.summary}</p>
        {item.recommendation && <div className="decision-recommendation"><Sparkles size={12} /><span>{item.recommendation}</span></div>}
        {item.evidence?.length ? <div className="decision-evidence">{item.evidence.slice(0, 2).map((evidence) => <span key={evidence}>{evidence}</span>)}</div> : null}
      </div>
      <button type="button" onClick={() => onNavigate(item.action, item.entity_id)}>
        {item.action_label}<ArrowRight size={13} />
      </button>
    </article>
  );
}
