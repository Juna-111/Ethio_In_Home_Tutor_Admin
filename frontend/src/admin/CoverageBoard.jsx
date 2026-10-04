import { useEffect, useState } from 'react';
import { AlertTriangle, BarChart3, RefreshCw } from 'lucide-react';
import { getAdminCoverageGaps } from '../services/api';

export default function CoverageBoard() {
  const [gaps, setGaps] = useState([]);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setState('loading');
    getAdminCoverageGaps()
      .then((result) => { if (active) { setGaps(result); setState('ready'); } })
      .catch((requestError) => { if (active) { setError(requestError.message || 'Could not load coverage data.'); setState('error'); } });
    return () => { active = false; };
  }, [refreshKey]);

  return (
    <section className="phase-view">
      <div className="view-heading">
        <div><p className="eyebrow">SUPPLY CORE <span>/</span> MARKET MAP</p><h2>Coverage gaps</h2></div>
        <button className="refresh-button" type="button" aria-label="Refresh coverage gaps" onClick={() => setRefreshKey((key) => key + 1)}><RefreshCw size={17} /></button>
      </div>
      <div className="coverage-intro"><BarChart3 size={20} /><span>Gap ratio is the share of pending demand without a verified, active tutor covering the same subject and subcity.</span></div>
      {error && <div className="inline-message inline-error" role="alert"><AlertTriangle size={16} />{error}</div>}
      <div className="data-table-wrap">
        <table className="data-table coverage-table">
          <thead><tr><th>AREA</th><th>SUBJECT</th><th>PENDING REQUESTS</th><th>ACTIVE TUTORS</th><th>SUPPLY GAP</th></tr></thead>
          <tbody>
            {state === 'loading' ? <tr><td colSpan="5" className="table-message">Loading coverage data…</td></tr>
              : gaps.length === 0 ? <tr><td colSpan="5" className="table-message">No pending demand to map.</td></tr>
                : gaps.map((gap) => (
                  <tr key={`${gap.subcity}-${gap.subject}`}>
                    <td><strong>{gap.subcity}</strong></td>
                    <td>{gap.subject}</td>
                    <td>{gap.pending_requests}</td>
                    <td>{gap.approved_tutors}</td>
                    <td><div className="gap-cell"><div className="gap-track"><span style={{ width: `${gap.gap_ratio * 100}%` }} /></div><strong>{Math.round(gap.gap_ratio * 100)}%</strong></div></td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}