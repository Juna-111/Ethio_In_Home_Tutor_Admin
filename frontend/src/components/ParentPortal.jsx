import React, { useState, useEffect } from 'react';
import { 
  ClipboardList, 
  Clock, 
  MapPin, 
  BookOpen, 
  Star, 
  MessageSquare, 
  Send, 
  Phone, 
  CheckCircle2, 
  AlertCircle,
  Loader2,
  RotateCw,
  X
} from 'lucide-react';
import { getParentMyRequests, submitParentFeedback, submitParentContactAdmin, cancelParentRequest } from '../services/api';

export default function ParentPortal({ user, lang, onSelectTab }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cancellingRequestId, setCancellingRequestId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [feedbackError, setFeedbackError] = useState(null);
  const [contactError, setContactError] = useState(null);

  // Feedback Modal State
  const [feedbackModal, setFeedbackModal] = useState(null); // { requestId, tutorName }
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  // Contact Admin Modal State
  const [contactModal, setContactModal] = useState(null); // { requestId }
  const [contactMsg, setContactMsg] = useState('');
  const [submittingContact, setSubmittingContact] = useState(false);
  const [contactSuccess, setContactSuccess] = useState(false);

  const loadRequests = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getParentMyRequests();
      setRequests(res.requests || res.items || []);
    } catch (err) {
      setError(err.message || 'Could not load your tutoring requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const handleCancelRequest = async (req) => {
    if (!window.confirm(lang === 'am' ? 'ይህን ጥያቄ መሰረዝ ይፈልጋሉ?' : 'Cancel this tutoring request?')) return;
    setActionError(null);
    setCancellingRequestId(req.id);
    try {
      await cancelParentRequest(req.id);
      await loadRequests();
    } catch (err) {
      setActionError(err.message || 'Could not cancel request.');
    } finally {
      setCancellingRequestId(null);
    }
  };

  const handleOpenFeedback = (req) => {
    setFeedbackModal({
      requestId: req.id,
      tutorName: req.assignment?.tutor_name || 'Tutor'
    });
    setRating(5);
    setComment('');
    setFeedbackSuccess(false);
    setFeedbackError(null);
  };

  const handleSendFeedback = async (e) => {
    e.preventDefault();
    if (!feedbackModal) return;
    setSubmittingFeedback(true);
    try {
      await submitParentFeedback({
        request_id: feedbackModal.requestId,
        rating: Number(rating),
        review_notes: comment.trim() || undefined
      });
      setFeedbackSuccess(true);
      setTimeout(() => {
        setFeedbackModal(null);
        setFeedbackSuccess(false);
      }, 1500);
    } catch (err) {
      setFeedbackError(err.message || 'Could not submit feedback.');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleOpenContact = (req) => {
    setContactModal({ requestId: req.id });
    setContactMsg('');
    setContactSuccess(false);
    setContactError(null);
  };

  const handleSendContact = async (e) => {
    e.preventDefault();
    if (!contactModal || !contactMsg.trim()) return;
    setSubmittingContact(true);
    try {
      await submitParentContactAdmin({
        request_id: contactModal.requestId,
        message: contactMsg.trim()
      });
      setContactSuccess(true);
      setTimeout(() => {
        setContactModal(null);
        setContactSuccess(false);
      }, 1500);
    } catch (err) {
      setContactError(err.message || 'Could not send your message.');
    } finally {
      setSubmittingContact(false);
    }
  };

  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'matched') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green/15 text-green">Matched</span>;
    }
    if (s === 'closed') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-muted/20 text-muted">Closed</span>;
    }
    if (s === 'cancelled') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-coral/10 text-coral">Cancelled</span>;
    }
    if (s === 'reviewing') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-citrus/20 text-citrus">Reviewing</span>;
    }
    return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-pine/10 text-pine">Pending</span>;
  };

  return (
    <div className="px-4 pb-12 space-y-4">
      <div className="bg-paper p-4 rounded-2xl border border-line shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-ink flex items-center space-x-2">
            <ClipboardList className="w-4 h-4 text-pine" />
            <span>{lang === 'am' ? 'የእኔ ጥያቄዎች' : 'My Tutoring Requests'}</span>
          </h2>
          <p className="text-xs text-muted mt-1">
            {lang === 'am' 
              ? 'ያስገቧቸውን የማጠናከሪያ ትምህርት ጥያቄዎች ሁኔታ እዚህ ይከታተሉ።' 
              : 'Track the status and matched tutors for your submitted requests.'}
          </p>
        </div>
        <button
          type="button"
          onClick={loadRequests}
          disabled={loading}
          className="p-2 rounded-xl border border-line hover:bg-line/40 text-muted hover:text-ink transition cursor-pointer shrink-0 ml-2"
          title={lang === 'am' ? 'አድስ' : 'Refresh'}
        >
          <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin text-pine' : ''}`} />
        </button>
      </div>

      {actionError && <div className="p-3 rounded-2xl bg-coral/10 border border-coral/20 text-coral text-xs" role="alert">{actionError}</div>}

      {loading ? (
        <div className="flex flex-col items-center justify-center p-8 bg-paper rounded-2xl border border-line text-muted">
          <Loader2 className="w-6 h-6 animate-spin text-pine mb-2" />
          <span className="text-xs">{lang === 'am' ? 'በመጫን ላይ...' : 'Loading your requests...'}</span>
        </div>
      ) : error ? (
        <div className="p-5 bg-paper rounded-2xl border border-line text-center space-y-3 shadow-sm">
          <div className="w-12 h-12 rounded-full bg-coral/10 text-coral mx-auto flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <p className="text-xs font-bold text-ink">
            {error.includes('authentication') || error.includes('401')
              ? (lang === 'am' ? 'የቴሌግራም ማረጋገጫ ያስፈልጋል' : 'Telegram Mini App Account Needed')
              : (lang === 'am' ? 'ጥያቄዎችን ማምጣት አልተቻለም' : 'Could Not Load Requests')}
          </p>
          <p className="text-xs text-muted leading-relaxed">
            {error.includes('authentication') || error.includes('401')
              ? (lang === 'am' 
                  ? 'የእርስዎን ጥያቄዎች ለማየት እባክዎ ይህን መተግበሪያ በቴሌግራም ውስጥ ይክፈቱት።' 
                  : 'Open MentorLink directly inside Telegram to view your account requests.')
              : error}
          </p>
          <div className="flex items-center justify-center space-x-2 pt-1">
            <button
              type="button"
              onClick={loadRequests}
              className="py-2 px-4 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm cursor-pointer"
            >
              {lang === 'am' ? 'እንደገና ይሞክሩ' : 'Retry'}
            </button>
            {onSelectTab && (
              <button
                type="button"
                onClick={() => onSelectTab('parent')}
                className="py-2 px-4 rounded-xl font-bold text-xs border border-line text-ink hover:bg-line/40 transition cursor-pointer"
              >
                {lang === 'am' ? 'አዲስ ጥያቄ ያስገቡ' : 'Post Request'}
              </button>
            )}
          </div>
        </div>
      ) : requests.length === 0 ? (
        <div className="p-8 bg-paper rounded-2xl border border-line text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-pine/10 text-pine mx-auto flex items-center justify-center">
            <ClipboardList className="w-6 h-6" />
          </div>
          <p className="text-xs text-ink font-bold">
            {lang === 'am' ? 'እስካሁን ምንም ጥያቄ አላስገቡም።' : 'No Tutoring Requests Yet'}
          </p>
          <p className="text-xs text-muted">
            {lang === 'am'
              ? 'ለልጅዎ ብቁ አስጠኚ ለማግኘት አዲስ ጥያቄ ያስገቡ።'
              : 'Post a request to find a vetted university tutor for your student.'}
          </p>
          {onSelectTab && (
            <button
              type="button"
              onClick={() => onSelectTab('parent')}
              className="mt-2 inline-flex items-center space-x-1.5 py-2.5 px-4 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>{lang === 'am' ? 'አስጠኚ ፈልግ (አዲስ ጥያቄ)' : 'Find a Tutor Now'}</span>
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((req) => (
            <div key={req.id} className="bg-paper p-4 rounded-2xl border border-line shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ink">Request #{req.id}</span>
                {getStatusBadge(req.status)}
              </div>

              <div className="text-xs text-muted space-y-1">
                <div className="flex items-center space-x-1.5">
                  <BookOpen className="w-3.5 h-3.5 text-pine shrink-0" />
                  <span className="text-ink font-semibold">{req.student_level}</span>
                  <span>•</span>
                  <span>{(req.subjects || []).join(', ')}</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <MapPin className="w-3.5 h-3.5 text-muted shrink-0" />
                  <span>{req.location_subcity}{req.location_landmark ? ` (${req.location_landmark})` : ''}</span>
                </div>
                <div className="flex items-center space-x-1.5 text-[11px]">
                  <Clock className="w-3 h-3 text-muted shrink-0" />
                  <span>Submitted {req.created_at ? new Date(req.created_at).toLocaleDateString() : '—'}</span>
                </div>
              </div>

              {/* Matched Tutor Card if available */}
              {(req.tutor_name || req.assignment) ? (
                <div className="bg-pine/5 border border-pine/15 rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-pine uppercase tracking-wider">
                      {lang === 'am' ? 'የተመደበ አስጠኚ' : 'Matched Tutor'}
                    </span>
                    <span className="text-[10px] font-bold text-green px-2 py-0.5 rounded bg-green/10">
                      {req.assignment?.status || 'Active'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-ink">{req.tutor_name || req.assignment?.tutor_name}</p>
                      <p className="text-[11px] text-muted">{req.tutor_university ? `${req.tutor_university} · ${req.tutor_department || ''}` : ((req.assignment?.tutor_subjects || []).join(', '))}</p>
                    </div>
                    {(req.tutor_phone || req.assignment?.tutor_phone) && (
                      <a
                        href={`tel:${req.tutor_phone || req.assignment?.tutor_phone}`}
                        className="p-2 rounded-xl bg-pine text-paper hover:bg-ink transition shadow-sm"
                        title="Call Tutor"
                      >
                        <Phone className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              ) : null}

              {/* Action Buttons */}
              <div className="flex items-center space-x-2 pt-1">
                {(req.status === 'pending' || req.status === 'reviewing') && (
                  <button
                    type="button"
                    onClick={() => handleCancelRequest(req)}
                    disabled={cancellingRequestId === req.id}
                    className="py-2 px-3 rounded-xl font-semibold text-xs border border-coral/30 text-coral hover:bg-coral/10 transition disabled:opacity-50"
                  >
                    {cancellingRequestId === req.id
                      ? (lang === 'am' ? 'በመሰረዝ ላይ...' : 'Cancelling...')
                      : (lang === 'am' ? 'ጥያቄ ሰርዝ' : 'Cancel Request')}
                  </button>
                )}

                {(req.status === 'matched' || req.status === 'closed') && (
                  <button
                    type="button"
                    onClick={() => handleOpenFeedback(req)}
                    className="flex-1 py-2 px-3 rounded-xl font-semibold text-xs bg-pine text-paper hover:bg-ink transition flex items-center justify-center space-x-1.5 shadow-sm"
                  >
                    <Star className="w-3.5 h-3.5 fill-citrus text-citrus" />
                    <span>{lang === 'am' ? 'አስተያየት ይስጡ' : 'Provide Feedback'}</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleOpenContact(req)}
                  className="py-2 px-3 rounded-xl font-semibold text-xs border border-line text-muted hover:text-ink hover:bg-white/60 transition flex items-center justify-center space-x-1"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>{lang === 'am' ? 'አስተዳዳሪን ያነጋግሩ' : 'Contact Support'}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Feedback Modal */}
      {feedbackModal && (
        <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-paper w-full max-w-sm rounded-3xl p-6 shadow-2xl relative border border-line text-left">
            <button
              onClick={() => setFeedbackModal(null)}
              className="absolute right-4 top-4 p-1.5 rounded-full text-muted hover:text-ink bg-line/60 transition"
            >
              <X className="w-4 h-4" />
            </button>

            <h3 className="text-base font-bold text-ink mb-1">
              Rate {feedbackModal.tutorName}
            </h3>
            <p className="text-xs text-muted mb-4">
              Your honest feedback helps us maintain top quality tutoring.
            </p>

            {feedbackSuccess ? (
              <div className="p-4 bg-green/10 border border-green/20 rounded-2xl text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-green mx-auto" />
                <p className="text-xs font-bold text-green">Thank you! Your feedback has been recorded.</p>
              </div>
            ) : (
              <form onSubmit={handleSendFeedback} className="space-y-4">
                {feedbackError && (
                  <div className="p-3 rounded-xl bg-coral/10 border border-coral/20 text-coral text-xs" role="alert">
                    {feedbackError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-ink mb-2">Rating</label>
                  <div className="flex items-center space-x-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onClick={() => setRating(star)}
                        className="p-1 transition hover:scale-110"
                      >
                        <Star
                          className={`w-7 h-7 ${
                            rating >= star ? 'text-citrus fill-citrus' : 'text-line'
                          }`}
                        />
                      </button>
                    ))}
                    <span className="text-xs font-bold text-citrus ml-2">{rating}/5 Stars</span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink mb-1">Comments / Review</label>
                  <textarea
                    rows={3}
                    placeholder="How was your tutor's punctuality, subject mastery, and communication?"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    className="w-full text-xs p-3 rounded-xl border border-line focus:outline-none focus:border-pine bg-white text-ink"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submittingFeedback}
                  className="w-full py-2.5 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm flex items-center justify-center space-x-1.5"
                >
                  {submittingFeedback ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>Submit Review</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Contact Admin Modal */}
      {contactModal && (
        <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-paper w-full max-w-sm rounded-3xl p-6 shadow-2xl relative border border-line text-left">
            <button
              onClick={() => setContactModal(null)}
              className="absolute right-4 top-4 p-1.5 rounded-full text-muted hover:text-ink bg-line/60 transition"
            >
              <X className="w-4 h-4" />
            </button>

            <h3 className="text-base font-bold text-ink mb-1">
              Contact Support
            </h3>
            <p className="text-xs text-muted mb-4">
              Need to change your schedule, subjects, or report an issue with Request #{contactModal.requestId}?
            </p>

            {contactSuccess ? (
              <div className="p-4 bg-green/10 border border-green/20 rounded-2xl text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-green mx-auto" />
                <p className="text-xs font-bold text-green">Message delivered to our support team.</p>
              </div>
            ) : (
              <form onSubmit={handleSendContact} className="space-y-4">
                {contactError && (
                  <div className="p-3 rounded-xl bg-coral/10 border border-coral/20 text-coral text-xs" role="alert">
                    {contactError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-ink mb-1">Message</label>
                  <textarea
                    rows={4}
                    required
                    placeholder="Type your message here..."
                    value={contactMsg}
                    onChange={(e) => setContactMsg(e.target.value)}
                    className="w-full text-xs p-3 rounded-xl border border-line focus:outline-none focus:border-pine bg-white text-ink"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submittingContact || !contactMsg.trim()}
                  className="w-full py-2.5 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm flex items-center justify-center space-x-1.5 disabled:opacity-60"
                >
                  {submittingContact ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>Send to Support</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
