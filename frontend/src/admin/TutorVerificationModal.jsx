import React, { useEffect, useState } from 'react';
import { X, CheckCircle, AlertCircle, FileText, Star, ThumbsDown, Loader2 } from 'lucide-react';
import { getAdminTutorDetail, getAdminTutorScorecard, updateAdminTutorVerification, rejectAdminTutor } from '../services/api';

export default function TutorVerificationModal({ tutorId, onClose, onUpdated }) {
  const [tutor, setTutor] = useState(null);
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectBox, setShowRejectBox] = useState(false);
  const [error, setError] = useState(null);

  const [checklist, setChecklist] = useState({
    id_verified: false,
    entrance_result_verified: false,
    phone_confirmed: false,
    claims_plausible: false,
  });

  useEffect(() => {
    if (!tutorId) return undefined;
    let active = true;
    setLoading(true);
    Promise.all([
      getAdminTutorDetail(tutorId),
      getAdminTutorScorecard(tutorId).catch(() => null),
    ])
      .then(([tutorData, scoreData]) => {
        if (!active) return;
        setTutor(tutorData);
        setScorecard(scoreData);
        if (tutorData.verification) {
          setChecklist({
            id_verified: Boolean(tutorData.verification.id_verified),
            entrance_result_verified: Boolean(tutorData.verification.entrance_result_verified),
            phone_confirmed: Boolean(tutorData.verification.phone_confirmed),
            claims_plausible: Boolean(tutorData.verification.claims_plausible),
          });
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || 'Could not load tutor details.');
        setLoading(false);
      });

    return () => { active = false; };
  }, [tutorId]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const allComplete = checklist.id_verified && checklist.entrance_result_verified && checklist.phone_confirmed && checklist.claims_plausible;

  const handleToggleCheck = (field) => {
    setChecklist((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const handleSaveVerification = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAdminTutorVerification(tutorId, checklist);
      setTutor((prev) => ({ ...prev, status: updated.tutor_status, verification: updated }));
      if (onUpdated) onUpdated(updated);
      setSaving(false);
    } catch (err) {
      setError(err.message || 'Failed to update verification.');
      setSaving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason || rejectReason.trim().length < 5) {
      setError('Please provide a rejection reason (minimum 5 characters).');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await rejectAdminTutor(tutorId, rejectReason.trim());
      setTutor((prev) => ({ ...prev, status: 'rejected' }));
      setShowRejectBox(false);
      if (onUpdated) onUpdated();
      setSaving(false);
    } catch (err) {
      setError(err.message || 'Failed to reject tutor.');
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="tutor-verification-title" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div>
            <p className="eyebrow">TUTOR VERIFICATION · ID #{tutorId}</p>
            <h2 id="tutor-verification-title">{tutor ? tutor.full_name : 'Loading Tutor...'}</h2>
          </div>
          <button className="modal-close-btn" type="button" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>

        {loading ? (
          <div className="modal-loading"><Loader2 className="spin" size={28} /></div>
        ) : error ? (
          <div className="modal-error"><AlertCircle size={20} /><span>{error}</span></div>
        ) : tutor ? (
          <div className="modal-body">
            <div className="tutor-stats-bar">
              <span className={`status-badge status-${tutor.status}`}>
                {tutor.status.toUpperCase()}
              </span>
              {scorecard && (
                <div className="scorecard-mini">
                  <span><Star size={14} className="star-icon" /> {scorecard.avg_rating ? scorecard.avg_rating.toFixed(1) : 'No ratings'}</span>
                  <span>{scorecard.feedback_count} feedback</span>
                  <span>{scorecard.response_rate !== null ? `${Math.round(scorecard.response_rate * 100)}% response` : 'No invites'}</span>
                  {scorecard.incident_count > 0 && (
                    <span className="incident-badge">{scorecard.incident_count} incident(s)</span>
                  )}
                </div>
              )}
            </div>

            <section className="detail-section">
              <h3>Academic & Experience</h3>
              <div className="detail-grid">
                <div><strong>University:</strong> {tutor.university} ({tutor.education_year})</div>
                <div><strong>Department:</strong> {tutor.department}</div>
                <div><strong>Experience:</strong> {tutor.years_of_experience} yrs</div>
                <div><strong>Expected Fee:</strong> {tutor.expected_fee_etb} ETB/hr</div>
                <div><strong>Base Subcity:</strong> {tutor.base_subcity}</div>
                <div><strong>Phone:</strong> <code>{tutor.phone_number}</code></div>
                <div><strong>Entrance Score:</strong> {tutor.entrance_result ?? 'N/A'}</div>
              </div>
              <div className="tag-row">
                <strong>Subjects:</strong>
                {(tutor.subjects_qualified || []).map((s) => (
                  <span className="tag" key={s}>{s}</span>
                ))}
              </div>
              {tutor.id_document_url && (
                <div className="document-link-row">
                  <FileText size={16} />
                  <a
                    href={`/api/v1/admin/tutors/${tutor.id}/document`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View Uploaded Credential Document
                  </a>
                </div>
              )}
            </section>

            <section className="checklist-section">
              <div className="section-title-row">
                <div>
                  <p className="eyebrow">QUALITY GATE</p>
                  <h3>Verification Checklist</h3>
                </div>
                <span className={`checklist-indicator ${allComplete ? 'complete' : 'pending'}`}>
                  {allComplete ? 'ALL CHECKS PASSED' : 'INCOMPLETE'}
                </span>
              </div>
              <p className="checklist-subtext">
                All 4 criteria must be explicitly verified before tutor status can transition to verified.
              </p>

              <div className="checklist-items">
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={checklist.id_verified}
                    onChange={() => handleToggleCheck('id_verified')}
                  />
                  <span>1. National ID or Student ID verified against photo and legal name</span>
                </label>
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={checklist.entrance_result_verified}
                    onChange={() => handleToggleCheck('entrance_result_verified')}
                  />
                  <span>2. University entrance exam score or transcript confirmed</span>
                </label>
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={checklist.phone_confirmed}
                    onChange={() => handleToggleCheck('phone_confirmed')}
                  />
                  <span>3. Active phone number confirmed reachable</span>
                </label>
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={checklist.claims_plausible}
                    onChange={() => handleToggleCheck('claims_plausible')}
                  />
                  <span>4. Education & subject capability claims plausible and vetted</span>
                </label>
              </div>

              <div className="checklist-actions">
                <button
                  className="btn-primary"
                  type="button"
                  onClick={handleSaveVerification}
                  disabled={saving}
                >
                  {saving ? <Loader2 className="spin" size={16} /> : <CheckCircle size={16} />}
                  <span>{allComplete ? 'Approve & Verify Tutor' : 'Save Checklist Progress'}</span>
                </button>

                {!showRejectBox ? (
                  <button
                    className="btn-danger-outline"
                    type="button"
                    onClick={() => setShowRejectBox(true)}
                  >
                    <ThumbsDown size={16} />
                    <span>Reject Tutor</span>
                  </button>
                ) : (
                  <div className="reject-box">
                    <textarea
                      placeholder="Reason for rejection (required)..."
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      rows={2}
                    />
                    <div className="reject-buttons">
                      <button className="btn-danger" type="button" onClick={handleReject} disabled={saving}>
                        Confirm Rejection
                      </button>
                      <button className="btn-subtle" type="button" onClick={() => setShowRejectBox(false)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
