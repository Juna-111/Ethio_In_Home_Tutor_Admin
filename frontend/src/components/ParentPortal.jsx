import React, { useState, useEffect, useMemo } from 'react';
import { 
  ClipboardList, 
  Clock, 
  MapPin, 
  BookOpen, 
  Star, 
  Bell, 
  CalendarDays, 
  ChevronRight, 
  GraduationCap, 
  Plus, 
  UsersRound, 
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


  const isAm = lang === 'am';

  const learners = useMemo(() => {
    const seen = new Map();
    requests.forEach((req) => {
      const name = req.student_name || req.child_name || req.learner_name || '';
      const key = name || `${req.student_level || ''}|${(req.subjects || []).join(',')}|${req.location_subcity || ''}`;
      if (!seen.has(key)) {
        seen.set(key, {
          key,
          name: name || `${isAm ? 'ተማሪ' : 'Learner'} ${seen.size + 1}`,
          level: req.student_level || '—',
          subjects: req.subjects || [],
          location: req.location_subcity || '',
          requests: 0,
        });
      }
      seen.get(key).requests += 1;
    });
    return Array.from(seen.values());
  }, [requests, isAm]);

  const matchedRequests = useMemo(() => requests.filter((req) => req.tutor_name || req.assignment), [requests]);
  const activeRequests = useMemo(
    () => requests.filter((req) => !['closed', 'cancelled'].includes((req.status || '').toLowerCase())),
    [requests]
  );
  const openRequests = useMemo(
    () => requests.filter((req) => ['pending', 'reviewing'].includes((req.status || '').toLowerCase())),
    [requests]
  );
  const activeTutor = matchedRequests.length
    ? (matchedRequests[0].tutor_name || matchedRequests[0].assignment?.tutor_name || '')
    : '';

  const schedules = useMemo(
    () => matchedRequests.map((req) => ({
      id: req.id,
      tutor: req.tutor_name || req.assignment?.tutor_name || 'Tutor',
      days: req.schedule_days || req.assignment?.schedule_days || [],
      time: req.time_slot || req.assignment?.time_slot || '—',
      duration: req.session_duration || req.assignment?.session_duration || '—',
      subjects: req.subjects || req.assignment?.tutor_subjects || [],
    })),
    [matchedRequests]
  );

  const notifications = useMemo(
    () => requests
      .slice()
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
      .slice(0, 4)
      .map((req) => {
        const status = (req.status || 'pending').toLowerCase();
        const tutor = req.tutor_name || req.assignment?.tutor_name;
        let title = isAm ? 'የጥያቄዎ ሁኔታ ተዘምኗል' : 'Request status updated';
        let body = isAm ? `ጥያቄ #${req.id}` : `Request #${req.id}`;
        if (status === 'matched' && tutor) {
          title = isAm ? 'አስጠኚ ተመድቧል' : 'Tutor matched';
          body = isAm ? `${tutor} ለጥያቄ #${req.id} ተመድቧል።` : `${tutor} was matched to Request #${req.id}.`;
        } else if (status === 'reviewing') {
          title = isAm ? 'ጥያቄዎ እየተገመገመ ነው' : 'Your request is being reviewed';
        }
        return { id: `${req.id}-${status}`, title, body, requestId: req.id, date: req.updated_at || req.created_at };
      }),
    [requests, isAm]
  );

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
    const confirmText = lang === 'am' ? 'ይህን ጥያቄ መሰረዝ ይፈልጋሉ?' : 'Cancel this tutoring request?';
    const tg = window.Telegram?.WebApp;
    const confirmed = tg?.showConfirm
      ? await new Promise((resolve) => tg.showConfirm(confirmText, resolve))
      : window.confirm(confirmText);
    if (!confirmed) return;
    try { tg?.HapticFeedback?.impactOccurred?.('light'); } catch (_) {}
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

      {/* Parent Portal 1.0 family dashboard */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-pine via-pine to-ink p-5 text-paper shadow-xl">
        <div className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-citrus/15 blur-2xl" />
        <div className="relative flex items-start justify-between gap-3">
          <div>
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.14em] text-paper/80">
              <UsersRound className="h-3 w-3 text-citrus" />
              {isAm ? 'የቤተሰብ ፖርታል' : 'Family portal'}
            </div>
            <h2 className="text-xl font-black tracking-tight">
              {user?.first_name
                ? (isAm ? `እንኳን ደህና መጡ, ${user.first_name}!` : `Welcome back, ${user.first_name}.`)
                : (isAm ? 'የቤተሰብዎን ትምህርት ያስተዳድሩ' : 'Manage your family learning')}
            </h2>
            <p className="mt-1.5 max-w-[310px] text-[11px] leading-relaxed text-paper/70">
              {isAm ? 'ጥያቄዎች፣ አስጠኚዎች እና የትምህርት ጊዜዎችዎ አንድ ቦታ ላይ።' : 'Requests, matched tutors and learning schedules in one private place.'}
            </p>
          </div>
          <button type="button" onClick={loadRequests} disabled={loading} className="rounded-xl border border-white/15 bg-white/10 p-2.5 text-paper/80">
            <RotateCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2">
          {[
            { value: learners.length, label: isAm ? 'ተማሪዎች' : 'Learners' },
            { value: activeRequests.length, label: isAm ? 'ንቁ ጥያቄዎች' : 'Active' },
            { value: matchedRequests.length, label: isAm ? 'የተመደቡ' : 'Matched' },
          ].map((item) => (
            <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 px-2 py-2.5 text-center">
              <div className="text-lg font-black text-citrus">{item.value}</div>
              <div className="text-[8px] font-bold text-paper/65">{item.label}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-2.5">
        <button type="button" onClick={() => onSelectTab?.('parent')} className="flex items-center gap-2.5 rounded-2xl border border-pine/15 bg-paper p-3 text-left shadow-sm">
          <span className="rounded-xl bg-pine/10 p-2 text-pine"><Plus className="h-4 w-4" /></span>
          <span><strong className="block text-[11px] font-black text-ink">{isAm ? 'አስጠኚ ፈልግ' : 'Find a tutor'}</strong><small className="block text-[9px] text-muted">{isAm ? 'አዲስ ጥያቄ' : 'Start a request'}</small></span>
        </button>
        <button type="button" onClick={() => document.getElementById('parent-request-list')?.scrollIntoView({ behavior: 'smooth' })} className="flex items-center gap-2.5 rounded-2xl border border-line bg-paper p-3 text-left shadow-sm">
          <span className="rounded-xl bg-citrus/15 p-2 text-citrus"><ClipboardList className="h-4 w-4" /></span>
          <span><strong className="block text-[11px] font-black text-ink">{isAm ? 'ጥያቄዎቼ' : 'My requests'}</strong><small className="block text-[9px] text-muted">{openRequests.length} {isAm ? 'ክፍት' : 'open'}</small></span>
        </button>
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="mb-3 flex items-start gap-2.5">
          <div className="rounded-xl bg-pine/10 p-2 text-pine"><UsersRound className="h-4 w-4" /></div>
          <div><h3 className="text-sm font-black text-ink">{isAm ? 'በጥያቄዎ ውስጥ ያሉ ተማሪዎች' : 'Learners in your requests'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'ከእርስዎ የትምህርት ጥያቄዎች የተገኘ አጭር ማጠቃለያ።' : 'A lightweight summary of learners represented by your tutoring requests.'}</p></div>
        </div>
        {learners.length ? (
          <div className="space-y-2">
            {learners.map((learner, index) => (
              <div key={learner.key} className="flex items-center gap-3 rounded-2xl border border-line bg-white/70 p-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-pine/10 text-xs font-black text-pine">{index + 1}</div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-black text-ink">{learner.name}</p>
                  <p className="mt-0.5 truncate text-[10px] text-muted">{learner.level} · {learner.subjects.join(', ') || '—'}</p>
                  {learner.location && <p className="mt-0.5 flex items-center gap-1 text-[9px] text-muted"><MapPin className="h-2.5 w-2.5" />{learner.location}</p>}
                </div>
                <span className="shrink-0 rounded-full bg-pine/5 px-2 py-1 text-[8px] font-bold text-pine">{learner.requests} {isAm ? 'ጥያቄ' : learner.requests === 1 ? 'request' : 'requests'}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-line p-4 text-center text-[10px] text-muted">{isAm ? 'የመጀመሪያውን ጥያቄ ሲያስገቡ ተማሪዎ እዚህ ይታያል።' : 'Your learners will appear here after you post a tutoring request.'}</div>
        )}
        <button type="button" onClick={() => onSelectTab?.('parent')} className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-line py-2 text-[10px] font-black text-pine">
          <Plus className="h-3 w-3" />{isAm ? 'ሌላ ተማሪ ጥያቄ ያክሉ' : 'Add another learner request'}<ChevronRight className="h-3 w-3" />
        </button>
      </section>

      {activeTutor && (
        <section className="rounded-3xl border border-pine/15 bg-gradient-to-br from-pine/5 to-paper p-4 shadow-sm">
          <div className="mb-3 flex items-start gap-2.5">
            <div className="rounded-xl bg-pine/10 p-2 text-pine"><GraduationCap className="h-4 w-4" /></div>
            <div><h3 className="text-sm font-black text-ink">{isAm ? 'የእኔ አስጠኚ' : 'My matched tutor'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'አሁን ከቤተሰብዎ ጋር የተገናኘው አስጠኚ።' : 'Your current tutor match.'}</p></div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-pine/10 bg-white/70 p-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine text-paper"><GraduationCap className="h-5 w-5" /></div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-black text-ink">{activeTutor}</p>
              <p className="mt-0.5 text-[10px] text-muted">{matchedRequests[0].tutor_university || matchedRequests[0].assignment?.tutor_university || (isAm ? 'የተረጋገጠ አስጠኚ' : 'Verified tutor')}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">{(matchedRequests[0].tutor_subjects || matchedRequests[0].assignment?.tutor_subjects || matchedRequests[0].subjects || []).slice(0, 4).map((subject) => <span key={subject} className="rounded-lg bg-pine/5 px-2 py-1 text-[8px] font-bold text-pine">{subject}</span>)}</div>
            </div>
            {(matchedRequests[0].tutor_phone || matchedRequests[0].assignment?.tutor_phone) && <a href={`tel:${matchedRequests[0].tutor_phone || matchedRequests[0].assignment?.tutor_phone}`} className="shrink-0 rounded-xl bg-pine p-2.5 text-paper"><Phone className="h-3.5 w-3.5" /></a>}
          </div>
        </section>
      )}

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="mb-3 flex items-start gap-2.5">
          <div className="rounded-xl bg-citrus/15 p-2 text-citrus"><CalendarDays className="h-4 w-4" /></div>
          <div><h3 className="text-sm font-black text-ink">{isAm ? 'የትምህርት ጊዜ ሰሌዳ' : 'Learning schedule'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'የተመደቡ አስጠኚዎችዎ የተጠየቁት ጊዜ።' : 'Your requested schedule for matched tutors.'}</p></div>
        </div>
        {schedules.length ? (
          <div className="space-y-2">{schedules.map((schedule) => (
            <div key={schedule.id} className="rounded-2xl border border-line bg-white/70 p-3">
              <div className="flex items-center justify-between gap-2"><p className="text-[10px] font-black text-pine">{schedule.tutor}</p><span className="text-[8px] font-bold text-muted">#{schedule.id}</span></div>
              <div className="mt-2 grid grid-cols-2 gap-2"><div className="rounded-xl bg-[#f1f3ef] p-2"><p className="text-[8px] font-bold text-muted">{isAm ? 'ቀናት' : 'Days'}</p><p className="mt-0.5 text-[10px] font-black text-ink">{schedule.days.length ? schedule.days.join(' · ') : '—'}</p></div><div className="rounded-xl bg-[#f1f3ef] p-2"><p className="text-[8px] font-bold text-muted">{isAm ? 'ሰዓት' : 'Time'}</p><p className="mt-0.5 text-[10px] font-black text-ink">{schedule.time}</p></div></div>
              <div className="mt-2 flex items-center gap-3 text-[9px] text-muted"><span className="flex items-center gap-1"><Clock className="h-3 w-3" />{schedule.duration}</span><span className="flex items-center gap-1"><BookOpen className="h-3 w-3" />{schedule.subjects.join(', ') || '—'}</span></div>
            </div>
          ))}</div>
        ) : <div className="rounded-2xl bg-[#f1f3ef] p-4 text-center text-[10px] text-muted">{isAm ? 'አስጠኚ ሲመደብ የጊዜ ሰሌዳው እዚህ ይታያል።' : 'Your schedule will appear here once a tutor is matched.'}</div>}
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="mb-3 flex items-start gap-2.5">
          <div className="rounded-xl bg-citrus/15 p-2 text-citrus"><Bell className="h-4 w-4" /></div>
          <div><h3 className="text-sm font-black text-ink">{isAm ? 'ማሳወቂያዎች' : 'Notifications'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'በጥያቄዎችዎ ላይ የቅርብ ጊዜ እንቅስቃሴ።' : 'Recent activity from your tutoring requests.'}</p></div>
        </div>
        {notifications.length ? <div className="space-y-1">{notifications.map((item) => (
          <button key={item.id} type="button" onClick={() => { setTimeout(() => document.getElementById('parent-request-list')?.scrollIntoView({ behavior: 'smooth' }), 0); }} className="flex w-full items-start gap-2.5 rounded-2xl p-2.5 text-left hover:bg-[#f1f3ef]">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-citrus/15 text-citrus"><Bell className="h-3.5 w-3.5" /></span>
            <span className="min-w-0 flex-1"><strong className="block text-[10px] font-black text-ink">{item.title}</strong><small className="mt-0.5 block text-[9px] text-muted">{item.body}</small><small className="mt-1 block text-[8px] font-bold text-muted">{item.date ? new Date(item.date).toLocaleDateString() : '—'}</small></span>
            <ChevronRight className="mt-2 h-3.5 w-3.5 shrink-0 text-muted" />
          </button>
        ))}</div> : <div className="rounded-2xl bg-[#f1f3ef] p-4 text-center text-[10px] text-muted">{isAm ? 'አዲስ ማሳወቂያ የለም።' : 'No notifications yet.'}</div>}
      </section>

      <div id="parent-request-list">
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
                  : 'Open Ethio In-Home Tutor directly inside Telegram to view your account requests.')
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

              {req.applications?.length > 0 && (
                <div className="bg-white border border-line rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-ink uppercase tracking-wider">
                      {lang === 'am' ? 'የአስጠኚ ምላሾች' : 'Tutor Responses'}
                    </span>
                    <span className="text-[10px] text-muted">{req.applications.length}</span>
                  </div>
                  <div className="space-y-1.5">
                    {req.applications.slice(0, 4).map((application) => (
                      <div key={application.invite_id} className="flex items-center justify-between text-xs">
                        <span className="text-ink font-medium">{application.tutor_name || `Tutor #${application.tutor_id}`}</span>
                        <span className="font-semibold text-muted capitalize">{application.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

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

                {(req.status === 'matched' || req.status === 'closed') && !req.has_feedback && (
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
        <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="parent-feedback-title">
          <div className="bg-paper w-full max-w-sm rounded-3xl p-6 shadow-2xl relative border border-line text-left">
            <button
              onClick={() => setFeedbackModal(null)}
              className="absolute right-4 top-4 p-1.5 rounded-full text-muted hover:text-ink bg-line/60 transition"
            >
              <X className="w-4 h-4" />
            </button>

            <h3 id="parent-feedback-title" className="text-base font-bold text-ink mb-1">
              {lang === 'am' ? `${feedbackModal.tutorName} ደረጃ ይስጡ` : `Rate ${feedbackModal.tutorName}`}
            </h3>
            <p className="text-xs text-muted mb-4">
              {lang === 'am' ? 'የእርስዎ አስተያየት የትምህርት ጥራታችንን ለማሻሻል ይረዳናል።' : 'Your honest feedback helps us maintain top quality tutoring.'}
            </p>

            {feedbackSuccess ? (
              <div className="p-4 bg-green/10 border border-green/20 rounded-2xl text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-green mx-auto" />
                <p className="text-xs font-bold text-green">{lang === 'am' ? 'እናመሰግናለን! አስተያየትዎ ተመዝግቧል።' : 'Thank you! Your feedback has been recorded.'}</p>
              </div>
            ) : (
              <form onSubmit={handleSendFeedback} className="space-y-4">
                {feedbackError && (
                  <div className="p-3 rounded-xl bg-coral/10 border border-coral/20 text-coral text-xs" role="alert">
                    {feedbackError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-ink mb-2">{lang === 'am' ? 'ደረጃ' : 'Rating'}</label>
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
                    <span className="text-xs font-bold text-citrus ml-2">{rating}/5 {lang === 'am' ? 'ኮከቦች' : 'Stars'}</span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink mb-1">{lang === 'am' ? 'አስተያየት / ግምገማ' : 'Comments / Review'}</label>
                  <textarea
                    rows={3}
                    placeholder={lang === 'am' ? 'የአስጠኚው ሰዓት አክባሪነት፣ የትምህርት ብቃት እና ግንኙነት እንዴት ነበር?' : "How was your tutor's punctuality, subject mastery, and communication?"}
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
                      <span>{lang === 'am' ? 'ግምገማ ይላኩ' : 'Submit Review'}</span>
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
        <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="parent-contact-title">
          <div className="bg-paper w-full max-w-sm rounded-3xl p-6 shadow-2xl relative border border-line text-left">
            <button
              onClick={() => setContactModal(null)}
              className="absolute right-4 top-4 p-1.5 rounded-full text-muted hover:text-ink bg-line/60 transition"
            >
              <X className="w-4 h-4" />
            </button>

            <h3 id="parent-contact-title" className="text-base font-bold text-ink mb-1">
              {lang === 'am' ? 'ድጋፍን ያነጋግሩ' : 'Contact Support'}
            </h3>
            <p className="text-xs text-muted mb-4">
              {lang === 'am' ? `የጊዜ ሰሌዳዎን ወይም የትምህርት ዓይነቶችን ለመቀየር ወይም በጥያቄ #${contactModal.requestId} ላይ ችግር ለማሳወቅ ይህን ቦታ ይጠቀሙ።` : `Need to change your schedule, subjects, or report an issue with Request #${contactModal.requestId}?`}
            </p>

            {contactSuccess ? (
              <div className="p-4 bg-green/10 border border-green/20 rounded-2xl text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-green mx-auto" />
                <p className="text-xs font-bold text-green">{lang === 'am' ? 'መልዕክትዎ ለድጋፍ ቡድናችን ተልኳል።' : 'Message delivered to our support team.'}</p>
              </div>
            ) : (
              <form onSubmit={handleSendContact} className="space-y-4">
                {contactError && (
                  <div className="p-3 rounded-xl bg-coral/10 border border-coral/20 text-coral text-xs" role="alert">
                    {contactError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-ink mb-1">{lang === 'am' ? 'መልዕክት' : 'Message'}</label>
                  <textarea
                    rows={4}
                    required
                    placeholder={lang === 'am' ? 'መልዕክትዎን እዚህ ይጻፉ...' : 'Type your message here...'}
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
                      <span>{lang === 'am' ? 'ለድጋፍ ይላኩ' : 'Send to Support'}</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
