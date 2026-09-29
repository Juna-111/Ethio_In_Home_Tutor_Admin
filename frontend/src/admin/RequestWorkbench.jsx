import { useEffect, useState } from 'react';
import { ArrowLeft, Check, ChevronLeft, ChevronRight, CircleAlert, LoaderCircle, Send, UserRoundCheck } from 'lucide-react';
import { SUBCITIES } from '../constants/options';
import {
  assignAdminTutor,
  closeAdminRequest,
  getAdminCandidates,
  getAdminRequest,
  getAdminRequests,
  pingAdminCandidates,
  waitlistAdminRequest,
} from '../services/api';

const FACTOR_LABELS = {
  subject_match: 'Subject',
  distance: 'Location',
  budget_fit: 'Budget',
  schedule_overlap: 'Schedule',
  experience: 'Experience',
};

function money(value) {
  return `${Number(value || 0).toLocaleString()} ETB`;
}

export default function RequestWorkbench({ initialRequestId }) {
  const [filters, setFilters] = useState({ status: 'pending', subcity: '', subject: '', page: 1 });
  const [list, setList] = useState({ items: [], total: 0, page: 1, page_size: 20 });
  const [selectedId, setSelectedId] = useState(initialRequestId || null);
  const [request, setRequest] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selectedTutorIds, setSelectedTutorIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (initialRequestId) setSelectedId(initialRequestId);
  }, [initialRequestId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getAdminRequests({ ...filters, page_size: 20 })
      .then((result) => {
        if (active) setList(result);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Could not load parent requests.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [filters, reloadKey]);

  useEffect(() => {
    if (!selectedId) {
      setRequest(null);
      setCandidates([]);
      return undefined;
    }
    let active = true;
    setDetailLoading(true);
    setError('');
    Promise.all([getAdminRequest(selectedId), getAdminCandidates(selectedId)])
      .then(([requestDetail, matchResult]) => {
        if (!active) return;
        setRequest(requestDetail);
        setCandidates(matchResult.candidates);
        setSelectedTutorIds([]);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Could not load request details.');
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => { active = false; };
  }, [selectedId, reloadKey]);

  const updateFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  };

  const toggleTutor = (tutorId) => {
    setSelectedTutorIds((current) => current.includes(tutorId)
      ? current.filter((id) => id !== tutorId)
      : [...current, tutorId]);
  };

  const runAction = async (action) => {
    setActionBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await action();
      setNotice(result.message);
      setSelectedTutorIds([]);
      setReloadKey((key) => key + 1);
    } catch (actionError) {
      setError(actionError.message || 'Action could not be completed.');
    } finally {
      setActionBusy(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(list.total / list.page_size));

  return (
    <section className="phase-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">SUPPLY CORE <span>/</span> REQUESTS</p>
          <h2>{selectedId ? 'Matching workbench' : 'Parent requests'}</h2>
        </div>
        {selectedId && (
          <button className="quiet-button" type="button" onClick={() => { setSelectedId(null); setNotice(''); }}>
            <ArrowLeft size={15} /> All requests
          </button>
        )}
      </div>

      {error && <div className="inline-message inline-error" role="alert"><CircleAlert size={16} />{error}</div>}
      {notice && <div className="inline-message inline-success" role="status"><Check size={16} />{notice}</div>}

      {!selectedId ? (
        <>
          <div className="filter-bar">
            <label>STATUS
              <select value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}>
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="matched">Matched</option>
                <option value="waitlisted">Waitlisted</option>
                <option value="closed">Closed</option>
              </select>
            </label>
            <label>SUBCITY
              <select value={filters.subcity} onChange={(event) => updateFilter('subcity', event.target.value)}>
                <option value="">All subcities</option>
                {SUBCITIES.map((subcity) => <option key={subcity} value={subcity}>{subcity}</option>)}
              </select>
            </label>
            <label>SUBJECT
              <input value={filters.subject} onChange={(event) => updateFilter('subject', event.target.value)} placeholder="Filter subjects" />
            </label>
          </div>
          <div className="data-table-wrap">
            <table className="data-table request-table">
              <thead><tr><th>REQUEST</th><th>STUDENT</th><th>SUBJECTS</th><th>AREA</th><th>BUDGET</th><th>STATUS</th><th /></tr></thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan="7" className="table-message">Loading requests…</td></tr>
                ) : list.items.length === 0 ? (
                  <tr><td colSpan="7" className="table-message">No requests match these filters.</td></tr>
                ) : list.items.map((item) => (
                  <tr
                    key={item.id}
                    className="request-row"
                    tabIndex={0}
                    onClick={() => setSelectedId(item.id)}
                    onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedId(item.id); } }}
                  >
                    <td><strong>REQ-{String(item.id).padStart(4, '0')}</strong><small>{item.parent_name}</small></td>
                    <td>{item.student_level}</td>
                    <td>{item.subjects.join(', ')}</td>
                    <td>{item.location_subcity}</td>
                    <td>{money(item.budget_etb)}</td>
                    <td><span className={`status-label status-${item.status}`}>{item.status}</span></td>
                    <td><ChevronRight size={16} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination-row">
            <span>{list.total ? `${(list.page - 1) * list.page_size + 1}–${Math.min(list.page * list.page_size, list.total)} of ${list.total}` : '0 requests'}</span>
            <div>
              <button className="icon-button" type="button" aria-label="Previous page" disabled={filters.page <= 1} onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}><ChevronLeft size={16} /></button>
              <span>Page {filters.page} / {totalPages}</span>
              <button className="icon-button" type="button" aria-label="Next page" disabled={filters.page >= totalPages} onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}><ChevronRight size={16} /></button>
            </div>
          </div>
        </>
      ) : detailLoading ? (
        <div className="empty-panel"><LoaderCircle className="spin" size={20} /> Loading request and candidates…</div>
      ) : request ? (
        <>
          <section className="request-summary">
            <div className="request-summary-main">
              <p className="eyebrow">REQUEST #{request.id}</p>
              <h3>{request.parent_name}</h3>
              <p>{request.student_level} <span>·</span> {request.subjects.join(', ')} <span>·</span> {request.location_subcity}</p>
            </div>
            <div className="request-summary-budget"><small>HOURLY BUDGET</small><strong>{money(request.budget_etb)}</strong></div>
          </section>
          <section className="request-facts" aria-label="Request details">
            <div><small>CONTACT</small><strong>{request.phone_number}</strong></div>
            <div><small>LANDMARK</small><strong>{request.location_landmark || 'Not provided'}</strong></div>
            <div><small>SCHEDULE</small><strong>{Array.isArray(request.schedule_days) ? request.schedule_days.join(', ') : request.schedule_days}</strong></div>
            <div><small>TIME</small><strong>{request.time_slot} · {request.session_duration}</strong></div>
            <div><small>TUTOR PREFERENCE</small><strong>{request.preferred_gender} · {request.preferred_experience}</strong></div>
          </section>
          {request.status === 'matched' && (
            <div style={{ background: 'var(--pine)', color: '#ffffff', padding: '12px 16px', borderRadius: '12px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600 }}>
              <UserRoundCheck size={18} />
              <span>Request #{request.id} has been matched and assigned to a mentor. Active in assignment pipeline.</span>
            </div>
          )}
          <section className="candidate-section">
            <div className="section-title-row candidate-title-row">
              <div><p className="eyebrow">MATCHING WORKBENCH</p><h3>Candidate comparison</h3></div>
              <button
                className="primary-button"
                type="button"
                disabled={actionBusy || selectedTutorIds.length === 0 || request.status !== 'pending'}
                onClick={() => runAction(() => pingAdminCandidates(request.id, selectedTutorIds))}
              ><Send size={15} /> Ping selected ({selectedTutorIds.length})</button>
            </div>
            {candidates.length === 0 ? <div className="empty-panel">No verified tutors currently match this request.</div> : (
              <div className="candidate-list">
                {candidates.map((candidate) => {
                  const canPing = candidate.telegram_available && !['sent', 'yes', 'no'].includes(candidate.invite_status);
                  const canAssign = request.status === 'pending';
                  return (
                    <article className="candidate-row" key={candidate.tutor_id}>
                      <div className="candidate-select">
                        <input type="checkbox" aria-label={`Select ${candidate.full_name} for ping`} checked={selectedTutorIds.includes(candidate.tutor_id)} disabled={!canPing || actionBusy || request.status !== 'pending'} onChange={() => toggleTutor(candidate.tutor_id)} />
                      </div>
                      <div className="candidate-identity">
                        <div className="candidate-name-line"><strong>{candidate.full_name}</strong><span className={`tier-tag tier-${candidate.tier}`}>{candidate.tier.replace('tier', 'TIER ')}</span></div>
                        <p>{candidate.university} · {candidate.department} · {candidate.base_subcity}</p>
                        <small>{candidate.matched_subjects.join(', ')} · {candidate.years_of_experience} yrs experience · {money(candidate.expected_fee_etb)}/hr</small>
                      </div>
                      <div className="candidate-score">
                        <strong>{Math.round(candidate.overall_score)}</strong><small>MATCH</small>
                      </div>
                      <div className="factor-grid">
                        {Object.entries(candidate.score_breakdown).map(([key, factor]) => (
                          <span className="factor-item" key={key} title={factor.explanation}>
                            <small>{FACTOR_LABELS[key]}</small><strong>{factor.score === null ? '—' : `${Math.round(factor.score)}%`}</strong>
                          </span>
                        ))}
                      </div>
                      <div className="candidate-actions">
                        {!candidate.telegram_available && <span className="muted-caption">No Telegram</span>}
                        {candidate.invite_status && <span className={`invite-state invite-${candidate.invite_status}`}>{candidate.invite_status === 'yes' ? 'Available' : candidate.invite_status === 'sent' ? 'Pinged' : candidate.invite_status === 'no' ? 'Unavailable' : candidate.invite_status}</span>}
                        <button className="secondary-button" type="button" disabled={!canAssign || actionBusy} onClick={() => runAction(() => assignAdminTutor(request.id, candidate.tutor_id))}>
                          <UserRoundCheck size={15} /> Assign
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
          {request.status === 'pending' && (
            <div className="request-admin-actions">
              <button className="quiet-button" type="button" disabled={actionBusy} onClick={() => runAction(() => waitlistAdminRequest(request.id))}>Move to waitlist</button>
              <button className="danger-button" type="button" disabled={actionBusy} onClick={() => runAction(() => closeAdminRequest(request.id))}>Close request</button>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}