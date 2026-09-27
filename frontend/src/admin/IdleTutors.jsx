import { useEffect, useState } from 'react';
import { BellRing, CircleAlert, RefreshCw } from 'lucide-react';
import { getAdminIdleTutors, nudgeAdminTutor } from '../services/api';

export default function IdleTutors() {
  const [days, setDays] = useState(14);
  const [tutors, setTutors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyTutor, setBusyTutor] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getAdminIdleTutors(days)
      .then((result) => { if (active) setTutors(result); })
      .catch((requestError) => { if (active) setError(requestError.message || 'Could not load idle tutors.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [days]);

  const nudge = async (tutorId) => {
    setBusyTutor(tutorId);
    setError('');
    setNotice('');
    try {
      const result = await nudgeAdminTutor(tutorId);
      setNotice(result.message);
    } catch (requestError) {
      setError(requestError.message || 'Could not send tutor nudge.');
    } finally {
      setBusyTutor(null);
    }
  };

  return (
    <section className="phase-view">
      <div className="view-heading">
        <div><p className="eyebrow">SUPPLY CORE <span>/</span> TUTOR ACTIVITY</p><h2>Idle tutors</h2></div>
        <label className="days-filter">IDLE FOR
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {[7, 14, 30, 60, 90].map((value) => <option key={value} value={value}>{value} days</option>)}
          </select>
        </label>
      </div>
      <p className="view-description">Verified, active tutors without an assignment in the selected period.</p>
      {error && <div className="inline-message inline-error" role="alert"><CircleAlert size={16} />{error}</div>}
      {notice && <div className="inline-message inline-success" role="status">{notice}</div>}
      <div className="idle-list">
        {loading ? <div className="table-message">Loading tutor activity…</div>
          : tutors.length === 0 ? <div className="empty-panel">No idle tutors found for this period.</div>
            : tutors.map((tutor) => (
              <article className="idle-row" key={tutor.id}>
                <div className="idle-avatar">{tutor.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</div>
                <div className="idle-details"><strong>{tutor.full_name}</strong><span>{tutor.base_subcity} · {tutor.subjects_qualified.join(', ')}</span><small>{tutor.last_assigned_at ? `Last assigned ${new Date(tutor.last_assigned_at).toLocaleDateString()}` : 'No assignment history'}</small></div>
                <button className="secondary-button" type="button" disabled={!tutor.telegram_user_id || busyTutor === tutor.id} onClick={() => nudge(tutor.id)} title={tutor.telegram_user_id ? 'Send Telegram nudge' : 'Tutor has no Telegram account'}>
                  <BellRing size={15} /> {busyTutor === tutor.id ? 'Sending…' : 'Nudge'}
                </button>
              </article>
            ))}
      </div>
    </section>
  );
}