import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, Search, ShieldCheck, Sparkles, GraduationCap, Activity, X } from 'lucide-react';
import { getAdminControlCenter, getAdminRequest, getAdminTutors } from '../services/api';
import './admin-control.css';

const fmt = (v) => new Intl.NumberFormat().format(v || 0);
const age = (h) => h == null ? '' : h < 1 ? 'just now' : h < 24 ? Math.round(h) + 'h waiting' : Math.floor(h / 24) + 'd ' + Math.round(h % 24) + 'h waiting';

export default function AdminControlCenter({ onNavigate }) {
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);

  const load = () => {
    setState('loading'); setError('');
    getAdminControlCenter().then((r) => { setData(r); setState('ready'); }).catch((e) => { setError(e.message || 'Control center unavailable.'); setState('error'); });
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
      } catch (_) { setResults({ tutors: [], request: null }); }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  if (state === 'loading') return <div className="control-loading"><div className="control-loading-line" /><div className="control-loading-line short" /><div className="control-loading-grid"><span /><span /><span /></div></div>;
  if (state === 'error') return <section className="control-error"><AlertTriangle size={20} /><div><strong>Control center unavailable</strong><p>{error}</p></div><button className="secondary-button" onClick={load}>Try again</button></section>;

  const attention = data.attention || [];
  const urgent = attention.filter((i) => i.severity === 'critical' || i.severity === 'high');

  return <section className="control-center">
    <div className="control-hero"><div><p className="eyebrow">ETHIO IN-HOME TUTOR · OPERATIONS</p><h1>Run the platform, not the paperwork.</h1><p className="control-hero-copy">The system watches matching, verification and assignments. You only step in where a human decision adds value.</p></div><div className="control-live"><span className="status-dot" /> LIVE CONTROL CENTER</div></div>

    <div className="control-search"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search a request number, tutor, or phone…" aria-label="Search admin records" />{query && <button type="button" aria-label="Clear search" onClick={() => setQuery('')}><X size={15} /></button>}</div>
    {results && <div className="control-search-results">
      {results.request && <button type="button" onClick={() => { setQuery(''); onNavigate('requests', results.request.id); }}><Activity size={17} /><span><strong>Request #{results.request.id}</strong><small>{results.request.parent_name} · {results.request.location_subcity}</small></span><ArrowRight size={15} /></button>}
      {results.tutors.map((t) => <button key={t.id} type="button" onClick={() => { setQuery(''); onNavigate('tutors', t.id); }}><GraduationCap size={17} /><span><strong>{t.full_name}</strong><small>{t.base_subcity} · {t.status}</small></span><ArrowRight size={15} /></button>)}
      {!results.request && !results.tutors.length && <div className="control-search-empty">No matching records.</div>}
    </div>}

    <div className="control-metrics">
      <Metric label="Waiting requests" value={data.pending_requests} tone="coral" icon={Clock3} />
      <Metric label="Tutors to verify" value={data.pending_tutors} tone="citrus" icon={GraduationCap} />
      <Metric label="Active tutoring" value={data.active_assignments} tone="green" icon={Activity} />
      <Metric label="Open incidents" value={data.open_incidents} tone={data.high_incidents ? 'coral' : 'blue'} icon={ShieldCheck} />
    </div>

    <div className="control-layout">
      <section className="control-panel attention-panel">
        <div className="control-panel-heading"><div><p className="eyebrow">HUMAN ATTENTION</p><h2>{urgent.length ? urgent.length + ' urgent decision' + (urgent.length === 1 ? '' : 's') : 'Nothing urgent'}</h2></div><span className="control-count">{attention.length}</span></div>
        {attention.length ? <div className="attention-list">{attention.map((item) => <AttentionItem key={item.id} item={item} onNavigate={onNavigate} />)}</div> : <div className="empty-attention"><CheckCircle2 size={24} /><strong>Operations are clear.</strong><span>No exception currently needs a human decision.</span></div>}
      </section>
      <aside className="control-side">
        <section className="control-panel next-move-panel"><p className="eyebrow">SYSTEM RECOMMENDATION</p><div className="recommendation-icon"><Sparkles size={19} /></div><h3>Next best move</h3><p>{data.next_move}</p>{attention[0] && <button className="primary-button" type="button" onClick={() => onNavigate(attention[0].action, attention[0].entity_id)}>{attention[0].action_label}<ArrowRight size={14} /></button>}</section>
        <section className="control-panel posture-panel"><div className="control-panel-heading"><div><p className="eyebrow">PLATFORM POSTURE</p><h3>Automation status</h3></div><CheckCircle2 size={18} /></div>{data.system_posture.map((line) => <div className="posture-line" key={line}><span className="posture-dot" />{line}</div>)}</section>
      </aside>
    </div>

    <section className="control-market-strip"><div><small>TODAY</small><strong>{fmt(data.requests_today)} new requests</strong></div><div><small>CONVERSION</small><strong>{data.conversion_rate_pct}%</strong></div><div><small>AVG. ASSIGNMENT</small><strong>{data.avg_days_to_assign} days</strong></div><button type="button" onClick={() => onNavigate('coverage')}>View marketplace health <ArrowRight size={14} /></button></section>
  </section>;
}

function Metric({ label, value, tone, icon: Icon }) { return <article className={'control-metric control-metric-' + tone}><div><small>{label}</small><Icon size={17} /></div><strong>{fmt(value)}</strong></article>; }
function AttentionItem({ item, onNavigate }) {
  const critical = item.severity === 'critical' || item.severity === 'high';
  return <article className={'attention-item attention-' + (critical ? 'critical' : 'attention')}>
    <div className="attention-mark">{critical ? <AlertTriangle size={17} /> : <Clock3 size={17} />}</div>
    <div className="attention-copy"><div className="attention-title"><strong>{item.title}</strong>{item.age_hours != null && <span>{age(item.age_hours)}</span>}</div><p>{item.summary}</p>{item.recommendation && <div className="attention-recommendation"><Sparkles size={13} /><span>{item.recommendation}</span></div>}{item.evidence?.length ? <div className="attention-evidence">{item.evidence.slice(0, 2).map((e) => <span key={e}>{e}</span>)}</div> : null}</div>
    <button type="button" onClick={() => onNavigate(item.action, item.entity_id)}>{item.action_label}<ArrowRight size={13} /></button>
  </article>;
}
