import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Award,
  Briefcase,
  CalendarDays,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Loader2,
  MapPin,
  Phone,
  RefreshCw,
  Save,
  ShieldCheck,
  UserRound,
  XCircle,
} from 'lucide-react';
import {
  getTutorMyAssignments,
  getTutorOpportunities,
  getTutorProfile,
  respondToTutorOpportunity,
  updateTutorAvailability,
} from '../services/api';

const DAYS = [
  ['Mon', 'Monday'],
  ['Tue', 'Tuesday'],
  ['Wed', 'Wednesday'],
  ['Thu', 'Thursday'],
  ['Fri', 'Friday'],
  ['Sat', 'Saturday'],
  ['Sun', 'Sunday'],
];

function normalizeAvailability(value) {
  if (!value) return { days: [], time: '' };
  if (typeof value === 'object' && !Array.isArray(value)) {
    return {
      days: Array.isArray(value.days) ? value.days : [],
      time: value.time || value.time_slot || '',
    };
  }
  if (Array.isArray(value)) {
    return { days: value, time: '' };
  }
  const text = String(value);
  const days = DAYS.map(([short]) => short).filter((day) => new RegExp('\\\\b' + day + '(?:day)?\\\\b', 'i').test(text));
  return { days, time: text };
}

function statusLabel(status, lang) {
  const map = {
    pending: lang === 'am' ? 'በመጠባበቅ ላይ' : 'Pending review',
    verified: lang === 'am' ? 'የተረጋገጠ' : 'Verified',
    probation: lang === 'am' ? 'በሙከራ' : 'Probation',
    rejected: lang === 'am' ? 'ውድቅ' : 'Rejected',
  };
  return map[(status || '').toLowerCase()] || status || '—';
}

export default function TutorPortal({ user, lang, onSelectTab }) {
  const isAm = lang === 'am';
  const [profile, setProfile] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState(null);
  const [savingAvailability, setSavingAvailability] = useState(false);
  const [respondingInvite, setRespondingInvite] = useState(null);
  const [availabilityOpen, setAvailabilityOpen] = useState(false);
  const [selectedDays, setSelectedDays] = useState([]);
  const [timeWindow, setTimeWindow] = useState('');

  const loadPortal = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const [profileRes, assignmentRes, opportunityRes] = await Promise.all([
        getTutorProfile(),
        getTutorMyAssignments(),
        getTutorOpportunities(),
      ]);
      setProfile(profileRes);
      setAssignments(assignmentRes?.assignments || assignmentRes?.items || []);
      setOpportunities(opportunityRes?.opportunities || []);
      const availability = normalizeAvailability(profileRes?.availability_schedule);
      setSelectedDays(availability.days);
      setTimeWindow(availability.time);
    } catch (err) {
      setActionError(err.message || (isAm ? 'ፖርታሉን መጫን አልተቻለም።' : 'Could not load your tutor portal.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPortal();
  }, []);

  const activeAssignments = useMemo(
    () => assignments.filter((item) => item.status === 'active'),
    [assignments]
  );
  const estimatedEarnings = useMemo(
    () => assignments.reduce((sum, item) => sum + Number(item.estimated_earnings_etb || 0), 0),
    [assignments]
  );

  const toggleDay = (day) => {
    setSelectedDays((current) =>
      current.includes(day) ? current.filter((item) => item !== day) : [...current, day]
    );
  };

  const saveAvailability = async () => {
    if (!selectedDays.length && !timeWindow.trim()) {
      setActionError(isAm ? 'ቢያንስ አንድ ቀን ወይም የጊዜ መረጃ ያስገቡ።' : 'Add at least a day or a time window.');
      return;
    }
    setSavingAvailability(true);
    setActionError(null);
    try {
      const updated = await updateTutorAvailability({
        days: selectedDays,
        time: timeWindow.trim(),
      });
      setProfile(updated);
      setAvailabilityOpen(false);
    } catch (err) {
      setActionError(err.message || (isAm ? 'የጊዜ ሰሌዳውን ማስቀመጥ አልተቻለም።' : 'Could not save availability.'));
    } finally {
      setSavingAvailability(false);
    }
  };

  const respond = async (inviteId, decision) => {
    setRespondingInvite(inviteId);
    setActionError(null);
    try {
      await respondToTutorOpportunity(inviteId, decision);
      await loadPortal();
    } catch (err) {
      setActionError(err.message || (isAm ? 'ምላሽዎን መላክ አልተቻለም።' : 'Could not respond to this opportunity.'));
      setRespondingInvite(null);
    }
  };

  if (loading) {
    return (
      <div className="px-4 pb-12">
        <div className="flex min-h-72 flex-col items-center justify-center rounded-3xl border border-line bg-paper text-muted shadow-sm">
          <Loader2 className="mb-2 h-7 w-7 animate-spin text-pine" />
          <span className="text-xs">{isAm ? 'የአስጠኚ ፖርታል በመጫን ላይ...' : 'Loading your tutor portal...'}</span>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="px-4 pb-12">
        <div className="rounded-3xl border border-line bg-paper p-6 text-center shadow-sm">
          <AlertCircle className="mx-auto mb-3 h-10 w-10 text-coral" />
          <h2 className="text-sm font-black text-ink">{isAm ? 'የአስጠኚ ፕሮፋይል አልተገኘም' : 'Tutor profile not found'}</h2>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            {isAm ? 'ተማሪዎችን ለመቀበል የአስጠኚ ምዝገባዎን ያጠናቅቁ።' : 'Complete tutor registration before receiving opportunities and assignments.'}
          </p>
          <button type="button" onClick={() => onSelectTab?.('tutor')} className="mt-4 rounded-xl bg-pine px-4 py-2.5 text-xs font-black text-paper">
            {isAm ? 'አስጠኚ ምዝገባ' : 'Complete Tutor Registration'}
          </button>
        </div>
      </div>
    );
  }

  const verification = profile.verification || {};
  const availability = normalizeAvailability(profile.availability_schedule);

  return (
    <div className="space-y-4 px-4 pb-12">
      {actionError && (
        <div className="flex items-start gap-2 rounded-2xl border border-coral/20 bg-coral/10 p-3 text-xs text-coral" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-pine via-pine to-ink p-5 text-paper shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-citrus/20 blur-2xl" />
        <div className="relative flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10">
            <GraduationCap className="h-6 w-6 text-citrus" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[9px] font-black uppercase tracking-[0.18em] text-paper/65">{isAm ? 'የአስጠኚ ፖርታል' : 'Tutor Portal'}</span>
            <h2 className="mt-1 truncate text-xl font-black">{profile.full_name}</h2>
            <p className="mt-1 text-[10px] text-paper/70">{profile.university} · {profile.department}</p>
          </div>
          <button type="button" onClick={loadPortal} className="rounded-xl border border-white/10 bg-white/10 p-2 text-paper/80" title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-2">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-2.5 text-center">
            <p className="text-lg font-black text-citrus">{activeAssignments.length}</p>
            <p className="text-[8px] font-bold text-paper/65">{isAm ? 'ንቁ ምደባ' : 'Active assignments'}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-2.5 text-center">
            <p className="text-lg font-black text-citrus">{opportunities.filter((item) => item.status === 'sent').length}</p>
            <p className="text-[8px] font-bold text-paper/65">{isAm ? 'እድሎች' : 'Opportunities'}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-2.5 text-center">
            <p className="text-lg font-black text-citrus">{profile.profile_completion_pct}%</p>
            <p className="text-[8px] font-bold text-paper/65">{isAm ? 'ፕሮፋይል' : 'Profile'}</p>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-pine/10 p-2 text-pine"><UserRound className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-black text-ink">{isAm ? 'የሙያ ፕሮፋይል' : 'Professional profile'}</h3>
            <p className="mt-0.5 text-[10px] text-muted">{isAm ? 'የትምህርት እና የማስጠናት ብቃትዎ።' : 'The information families and the matching team use to understand your fit.'}</p>
          </div>
          <span className="rounded-full bg-pine/10 px-2 py-1 text-[9px] font-black text-pine">{statusLabel(profile.status, lang)}</span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-muted">Education</span><strong className="mt-1 block text-ink">{profile.education_year}</strong></div>
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-muted">Experience</span><strong className="mt-1 block text-ink">{profile.years_of_experience} {isAm ? 'ዓመት' : 'years'}</strong></div>
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-muted">Subjects</span><strong className="mt-1 block text-ink">{(profile.subjects_qualified || []).join(', ') || '—'}</strong></div>
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-muted">Grades</span><strong className="mt-1 block text-ink">{(profile.grades_qualified || []).join(', ') || '—'}</strong></div>
        </div>

        <div className="mt-2 flex items-center gap-2 rounded-2xl border border-line p-3 text-[10px]">
          <MapPin className="h-4 w-4 shrink-0 text-pine" />
          <span className="min-w-0 flex-1"><span className="text-muted">{isAm ? 'መሠረት / ሽፋን' : 'Base / coverage'}</span><strong className="mt-0.5 block text-ink">{profile.base_subcity} · {(profile.coverage_areas || []).join(', ')}</strong></span>
          <span className="font-black text-pine">{Number(profile.expected_fee_etb || 0).toLocaleString()} ETB/hr</span>
        </div>
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-citrus/15 p-2 text-citrus"><ShieldCheck className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-black text-ink">{isAm ? 'የማረጋገጫ ሁኔታ' : 'Verification status'}</h3>
            <p className="mt-0.5 text-[10px] text-muted">{isAm ? 'የአስጠኚዎን መተማመኛ የሚጠናክር የማረጋገጫ ዝርዝር።' : 'A clear checklist for your tutor verification.'}</p>
          </div>
          {verification.checklist_complete ? <CheckCircle2 className="h-5 w-5 text-green" /> : <Clock3 className="h-5 w-5 text-citrus" />}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[
            [verification.id_verified, isAm ? 'መታወቂያ' : 'ID verified'],
            [verification.entrance_result_verified, isAm ? 'የፈተና ውጤት' : 'Result checked'],
            [verification.phone_confirmed, isAm ? 'ስልክ' : 'Phone confirmed'],
            [verification.claims_plausible, isAm ? 'መረጃ' : 'Profile reviewed'],
          ].map(([done, label]) => (
            <div key={label} className="flex items-center gap-2 rounded-xl border border-line p-2.5 text-[9px] font-bold">
              {done ? <CheckCircle2 className="h-3.5 w-3.5 text-green" /> : <Clock3 className="h-3.5 w-3.5 text-muted" />}
              <span className={done ? 'text-ink' : 'text-muted'}>{label}</span>
            </div>
          ))}
        </div>
        {profile.is_paused && <div className="mt-2 rounded-xl bg-coral/10 p-2.5 text-[9px] font-bold text-coral">{isAm ? 'ፕሮፋይልዎ ለጊዜው ቆሟል።' : 'Your tutor profile is currently paused and will not receive new matches.'}</div>}
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-citrus/15 p-2 text-citrus"><CalendarDays className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-black text-ink">{isAm ? 'የመገኘት ካሌንደር' : 'Availability calendar'}</h3>
            <p className="mt-0.5 text-[10px] text-muted">{isAm ? 'በምትመርጧቸው ቀናት የሚገኙበትን ሰዓት ያዘምኑ።' : 'Keep your weekly availability current for better matching.'}</p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {DAYS.map(([short, full]) => (
            <button
              key={short}
              type="button"
              onClick={() => toggleDay(short)}
              className={`rounded-xl border px-2.5 py-2 text-[9px] font-black transition ${selectedDays.includes(short) ? 'border-citrus bg-citrus/20 text-ink' : 'border-line text-muted'}`}
              title={full}
            >
              {short}
            </button>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-2xl bg-[#f1f3ef] p-3">
          <Clock3 className="h-4 w-4 text-pine" />
          <input
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            placeholder={isAm ? 'ለምሳሌ፡ 5 PM - 8 PM' : 'e.g. 5 PM - 8 PM'}
            className="min-w-0 flex-1 bg-transparent text-xs font-semibold text-ink outline-none"
          />
        </div>
        <button type="button" onClick={saveAvailability} disabled={savingAvailability} className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-2.5 text-xs font-black text-paper disabled:opacity-60">
          {savingAvailability ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {isAm ? 'የጊዜ ሰሌዳ አስቀምጥ' : 'Save availability'}
        </button>
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-pine/10 p-2 text-pine"><Briefcase className="h-4 w-4" /></div>
          <div><h3 className="text-sm font-black text-ink">{isAm ? 'የማስተማር እድሎች' : 'Tutor opportunities'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'ከቤተሰቦች የተላኩ አዲስ የማስጠናት እድሎች።' : 'Real opportunities sent to you by the matching team.'}</p></div>
        </div>
        <div className="mt-3 space-y-2">
          {opportunities.length ? opportunities.map((item) => (
            <div key={item.invite_id} className="rounded-2xl border border-line p-3">
              <div className="flex items-start justify-between gap-2">
                <div><span className="text-[9px] font-black uppercase tracking-wider text-pine">#{item.request_id}</span><p className="mt-1 text-xs font-black text-ink">{item.student_level} · {item.subjects.join(', ')}</p></div>
                <span className={`rounded-full px-2 py-1 text-[8px] font-black ${item.status === 'yes' ? 'bg-green/10 text-green' : item.status === 'no' ? 'bg-coral/10 text-coral' : 'bg-citrus/15 text-ink'}`}>
                  {item.status === 'yes' ? (isAm ? 'ተቀብሏል' : 'Accepted') : item.status === 'no' ? (isAm ? 'አልተቀበለም' : 'Declined') : (isAm ? 'አዲስ' : 'New')}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[9px]">
                <span className="rounded-xl bg-[#f1f3ef] p-2"><MapPin className="mr-1 inline h-3 w-3 text-pine" />{item.location}</span>
                <span className="rounded-xl bg-[#f1f3ef] p-2"><CalendarDays className="mr-1 inline h-3 w-3 text-pine" />{item.schedule}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <strong className="text-xs text-ink">{Number(item.budget_etb || 0).toLocaleString()} ETB/hr</strong>
                {item.status === 'sent' && (
                  <div className="flex gap-1.5">
                    <button type="button" disabled={respondingInvite === item.invite_id} onClick={() => respond(item.invite_id, 'no')} className="rounded-xl border border-line p-2 text-coral"><XCircle className="h-4 w-4" /></button>
                    <button type="button" disabled={respondingInvite === item.invite_id} onClick={() => respond(item.invite_id, 'yes')} className="rounded-xl bg-pine p-2 text-paper"><CheckCircle2 className="h-4 w-4" /></button>
                  </div>
                )}
              </div>
            </div>
          )) : <div className="rounded-2xl bg-[#f1f3ef] p-4 text-center text-[10px] text-muted">{isAm ? 'እስካሁን አዲስ እድል የለም።' : 'No tutoring opportunities yet.'}</div>}
        </div>
      </section>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-citrus/15 p-2 text-citrus"><Award className="h-4 w-4" /></div>
          <div><h3 className="text-sm font-black text-ink">{isAm ? 'የተመደቡ ተማሪዎች' : 'My assignments'}</h3><p className="mt-0.5 text-[10px] text-muted">{isAm ? 'ንቁ ምደባዎችዎን እና የተገመተ ገቢዎን ይከታተሉ።' : 'Manage your active students and assignment history.'}</p></div></div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-[9px] text-muted">Active</span><strong className="mt-1 block text-lg font-black text-pine">{activeAssignments.length}</strong></div>
          <div className="rounded-2xl bg-[#f1f3ef] p-3"><span className="text-[9px] text-muted">Est. earnings</span><strong className="mt-1 block text-sm font-black text-ink">{Math.round(estimatedEarnings).toLocaleString()} ETB</strong></div>
        </div>

        <div className="mt-3 space-y-2">
          {assignments.length ? assignments.map((item) => (
            <div key={item.assignment_id} className="rounded-2xl border border-line p-3">
              <div className="flex items-center justify-between gap-2">
                <div><span className="text-[9px] font-black uppercase tracking-wider text-pine">Assignment #{item.assignment_id}</span><p className="mt-1 text-xs font-black text-ink">{item.student_name_context}</p></div>
                <span className="rounded-full bg-pine/10 px-2 py-1 text-[8px] font-black text-pine">{item.status}</span>
              </div>
              <div className="mt-2 space-y-1 text-[9px] text-muted">
                <p><GraduationCap className="mr-1 inline h-3 w-3 text-pine" />{item.student_level} · {(item.subjects || []).join(', ')}</p>
                <p><MapPin className="mr-1 inline h-3 w-3" />{item.location}</p>
                <p><CalendarDays className="mr-1 inline h-3 w-3" />{item.schedule}</p>
              </div>
              <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
                <span className="text-[9px] text-muted">{item.sessions_completed || 0} {isAm ? 'ጊዜ' : 'sessions'} · {item.avg_rating ? `${item.avg_rating}/5` : '—'}</span>
                {item.parent_phone && <a href={`tel:${item.parent_phone}`} className="rounded-xl bg-pine p-2 text-paper" aria-label={isAm ? 'ወላጅን ይደውሉ' : 'Call parent'}><Phone className="h-3.5 w-3.5" /></a>}
              </div>
            </div>
          )) : <div className="rounded-2xl bg-[#f1f3ef] p-4 text-center text-[10px] text-muted">{isAm ? 'እስካሁን ተማሪ አልተመደበልዎትም።' : 'No student assignments yet.'}</div>}
        </div>
      </section>
    </div>
  );
}
