import React, { useEffect, useState } from 'react';
import { AlertCircle, CalendarClock, CheckCircle2, Clock3, Loader2, Plus, RefreshCw, Save } from 'lucide-react';
import { createTutorSession, getParentSessions, getTutorSessions, updateTutorSession } from '../services/api';

const copy = {
  en: {
    titleTutor: 'Sessions & lesson logs',
    titleParent: 'Lessons & learning updates',
    introTutor: 'Schedule lessons, record attendance, and share clear progress notes with families.',
    introParent: 'Review upcoming lessons, attendance, notes, and homework shared by your tutor.',
    assignment: 'Assignment', date: 'Date and time', duration: 'Minutes', topic: 'Lesson topic',
    create: 'Schedule lesson', scheduled: 'Scheduled', completed: 'Completed', cancelled: 'Cancelled',
    pending: 'Attendance pending', present: 'Present', absent: 'Absent', excused: 'Excused',
    notes: 'Lesson notes', homework: 'Homework / next steps', save: 'Save lesson log',
    emptyTutor: 'No lessons yet. Schedule the first session for an active assignment.',
    emptyParent: 'No sessions have been scheduled yet.',
    chooseAssignment: 'Choose an active assignment', loadError: 'Could not load sessions.',
    saved: 'Lesson log saved.', required: 'Choose an assignment, date, and topic.',
    noAssignments: 'You need an active assignment before scheduling lessons.',
    mins: 'minutes', refresh: 'Refresh',
  },
  am: {
    titleTutor: 'የትምህርት ቀጠሮዎች እና መዝገቦች',
    titleParent: 'የትምህርት ሁኔታ እና ዝመናዎች',
    introTutor: 'ቀጠሮ ይያዙ፣ መገኘትን ይመዝግቡ፣ የትምህርት ማስታወሻዎችን ያጋሩ።',
    introParent: 'የትምህርት ቀጠሮ፣ መገኘት፣ ማስታወሻ እና የቤት ስራ ይመልከቱ።',
    assignment: 'ምደባ', date: 'ቀን እና ሰዓት', duration: 'ደቂቃ', topic: 'የትምህርት ርዕስ',
    create: 'ቀጠሮ ያስይዙ', scheduled: 'ተይዟል', completed: 'ተጠናቋል', cancelled: 'ተሰርዟል',
    pending: 'መገኘት አልተመዘገበም', present: 'ተገኝቷል', absent: 'አልተገኘም', excused: 'በምክንያት ቀርቷል',
    notes: 'የትምህርት ማስታወሻ', homework: 'የቤት ስራ / ቀጣይ እርምጃ', save: 'መዝገብ አስቀምጥ',
    emptyTutor: 'እስካሁን ቀጠሮ የለም። ለንቁ ምደባ ቀጠሮ ያስይዙ።',
    emptyParent: 'እስካሁን ቀጠሮ አልተያዘም።',
    chooseAssignment: 'ንቁ ምደባ ይምረጡ', loadError: 'ቀጠሮዎችን መጫን አልተቻለም።',
    saved: 'የትምህርት መዝገብ ተቀምጧል።', required: 'ምደባ፣ ቀን እና ርዕስ ይምረጡ።',
    noAssignments: 'ቀጠሮ ለመያዝ ንቁ ምደባ ያስፈልጋል.',
    mins: 'ደቂቃ', refresh: 'አድስ',
  },
};

function initialForm() {
  return { assignment_id: '', scheduled_at: '', duration_minutes: '60', lesson_topic: '' };
}

export default function SessionManager({ mode = 'tutor', assignments = [], lang = 'en' }) {
  const isParent = mode === 'parent';
  const t = copy[lang] || copy.en;
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState(initialForm);
  const [logs, setLogs] = useState({});

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const result = isParent ? await getParentSessions() : await getTutorSessions();
      const items = result.sessions || [];
      setSessions(items);
      setLogs(Object.fromEntries(items.map((item) => [item.id, {
        status: item.status,
        attendance: item.attendance,
        lesson_notes: item.lesson_notes || '',
        homework: item.homework || '',
      }])));
    } catch (err) {
      setError(err.message || t.loadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [mode]);

  const setLogField = (id, field, value) => {
    setLogs((current) => ({ ...current, [id]: { ...current[id], [field]: value } }));
  };

  const schedule = async (event) => {
    event.preventDefault();
    if (!form.assignment_id || !form.scheduled_at || form.lesson_topic.trim().length < 2) {
      setError(t.required);
      return;
    }
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await createTutorSession(Number(form.assignment_id), {
        scheduled_at: new Date(form.scheduled_at).toISOString(),
        duration_minutes: Number(form.duration_minutes),
        lesson_topic: form.lesson_topic.trim(),
      });
      setForm(initialForm());
      setNotice(t.saved);
      await load();
    } catch (err) {
      setError(err.message || t.loadError);
    } finally {
      setBusy(false);
    }
  };

  const saveLog = async (session) => {
    const value = logs[session.id] || {};
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await updateTutorSession(session.id, {
        status: value.status,
        attendance: value.attendance,
        lesson_notes: value.lesson_notes,
        homework: value.homework,
      });
      setNotice(t.saved);
      await load();
    } catch (err) {
      setError(err.message || t.loadError);
    } finally {
      setBusy(false);
    }
  };

  const labelForStatus = (value) => value === 'completed' ? t.completed : value === 'cancelled' ? t.cancelled : t.scheduled;
  const attendanceLabel = (value) => ({ pending: t.pending, present: t.present, absent: t.absent, excused: t.excused }[value] || value);

  return (
    <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-pine/10 p-2 text-pine"><CalendarClock className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-black text-ink">{isParent ? t.titleParent : t.titleTutor}</h3>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">{isParent ? t.introParent : t.introTutor}</p>
        </div>
        <button type="button" onClick={load} disabled={loading} className="rounded-xl border border-line p-2 text-pine" aria-label={t.refresh}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCwIcon />}
        </button>
      </div>

      {error && <div role="alert" className="mt-3 flex gap-2 rounded-xl border border-coral/20 bg-coral/10 p-3 text-[10px] text-coral"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="mt-3 flex gap-2 rounded-xl bg-green/10 p-3 text-[10px] text-green"><CheckCircle2 className="h-4 w-4 shrink-0" />{notice}</div>}

      {!isParent && (
        <form onSubmit={schedule} className="mt-4 space-y-2 rounded-2xl bg-canvas p-3">
          <label className="block text-[10px] font-bold text-muted">{t.assignment}
            <select value={form.assignment_id} onChange={(e) => setForm((v) => ({ ...v, assignment_id: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" required>
              <option value="">{t.chooseAssignment}</option>
              {assignments.filter((item) => item.status === 'active').map((item) => <option key={item.assignment_id} value={item.assignment_id}>#{item.assignment_id} · {item.student_name_context}</option>)}
            </select>
          </label>
          {!assignments.some((item) => item.status === 'active') && <p className="text-[10px] text-muted">{t.noAssignments}</p>}
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-[10px] font-bold text-muted">{t.date}
              <input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm((v) => ({ ...v, scheduled_at: e.target.value }))} className="mt-1 w-full min-w-0 rounded-xl border border-line bg-paper p-2 text-xs text-ink" required />
            </label>
            <label className="block text-[10px] font-bold text-muted">{t.duration}
              <input type="number" min="15" max="240" step="15" value={form.duration_minutes} onChange={(e) => setForm((v) => ({ ...v, duration_minutes: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2 text-xs text-ink" required />
            </label>
          </div>
          <label className="block text-[10px] font-bold text-muted">{t.topic}
            <input value={form.lesson_topic} onChange={(e) => setForm((v) => ({ ...v, lesson_topic: e.target.value }))} minLength="2" maxLength="200" className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" required />
          </label>
          <button type="submit" disabled={busy || loading || !assignments.some((item) => item.status === 'active')} className="flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-2.5 text-xs font-black text-paper disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{t.create}
          </button>
        </form>
      )}

      <div className="mt-4 space-y-2">
        {loading ? <div className="flex items-center justify-center gap-2 rounded-2xl bg-canvas p-5 text-xs text-muted"><Loader2 className="h-4 w-4 animate-spin" />Loading...</div> :
          sessions.length ? sessions.map((session) => {
            const value = logs[session.id] || {};
            return (
              <article key={session.id} className="rounded-2xl border border-line p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-black text-ink">{session.lesson_topic}</p>
                    <p className="mt-1 text-[10px] text-muted">{new Date(session.scheduled_at).toLocaleString()} · {session.duration_minutes} {t.mins}</p>
                    <p className="mt-1 text-[10px] text-muted">{t.assignment} #{session.assignment_id}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-pine/10 px-2 py-1 text-[9px] font-black text-pine">{labelForStatus(session.status)}</span>
                </div>
                {isParent ? (
                  <div className="mt-3 space-y-2 border-t border-line pt-3 text-[10px]">
                    <p><strong className="text-ink">{attendanceLabel(session.attendance)}</strong></p>
                    {session.lesson_notes && <p className="whitespace-pre-wrap text-muted">{session.lesson_notes}</p>}
                    {session.homework && <p className="rounded-xl bg-canvas p-2 text-ink"><strong>{t.homework}: </strong>{session.homework}</p>}
                  </div>
                ) : (
                  <div className="mt-3 space-y-2 border-t border-line pt-3">
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-[10px] font-bold text-muted">{t.attendance || 'Attendance'}
                        <select value={value.attendance || 'pending'} disabled={session.status === 'cancelled'} onChange={(e) => setLogField(session.id, 'attendance', e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-paper p-2 text-[10px] text-ink">
                          {['pending', 'present', 'absent', 'excused'].map((item) => <option key={item} value={item}>{attendanceLabel(item)}</option>)}
                        </select>
                      </label>
                      <label className="text-[10px] font-bold text-muted">Status
                        <select value={value.status || 'scheduled'} onChange={(e) => setLogField(session.id, 'status', e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-paper p-2 text-[10px] text-ink" disabled={session.status === 'cancelled' || session.status === 'completed'}>
                          {['scheduled', 'completed', 'cancelled'].map((item) => <option key={item} value={item}>{labelForStatus(item)}</option>)}
                        </select>
                      </label>
                    </div>
                    <label className="block text-[10px] font-bold text-muted">{t.notes}
                      <textarea rows="2" maxLength="5000" value={value.lesson_notes || ''} disabled={session.status === 'cancelled'} onChange={(e) => setLogField(session.id, 'lesson_notes', e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" />
                    </label>
                    <label className="block text-[10px] font-bold text-muted">{t.homework}
                      <textarea rows="2" maxLength="3000" value={value.homework || ''} disabled={session.status === 'cancelled'} onChange={(e) => setLogField(session.id, 'homework', e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" />
                    </label>
                    <button type="button" onClick={() => saveLog(session)} disabled={busy || session.status === 'cancelled'} className="flex w-full items-center justify-center gap-2 rounded-xl border border-line bg-paper py-2.5 text-xs font-black text-pine disabled:opacity-50">
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t.save}
                    </button>
                  </div>
                )}
              </article>
            );
          }) : <div className="rounded-2xl bg-canvas p-4 text-center text-[10px] text-muted">{isParent ? t.emptyParent : t.emptyTutor}</div>}
      </div>
    </section>
  );
}

function RefreshCwIcon() {
  return <RefreshCw className="h-4 w-4" />;
}
