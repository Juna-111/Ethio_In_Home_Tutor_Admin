import React, { useEffect, useState } from 'react';
import { AlertCircle, BookOpenCheck, CheckCircle2, ClipboardCheck, Loader2, Plus, Save } from 'lucide-react';
import {
  createLearnerProfile,
  createTutorAssessment,
  getLearnerProfiles,
  getParentAssessments,
  updateLearnerProfile,
} from '../services/api';

const text = {
  en: {
    parentTitle: 'Learner profiles & progress',
    tutorTitle: 'Diagnostic assessments',
    parentIntro: 'Keep learning goals and support preferences in one private place. Your tutor’s assessment updates appear below.',
    tutorIntro: 'Record a baseline or progress check for an active assignment. Parents can review the results in their portal.',
    name: 'Learner name', level: 'Current grade / level', subjects: 'Subjects', goals: 'Learning goals',
    strengths: 'Strengths', focus: 'Focus areas', preferences: 'Learning preferences', create: 'Create profile',
    save: 'Save profile', emptyProfiles: 'No learner profiles yet.', emptyAssessments: 'No diagnostic assessments yet.',
    subject: 'Assessed subject', type: 'Assessment type', baseline: 'Baseline', progress: 'Progress check',
    score: 'Score (%)', notes: 'Tutor notes', next: 'Recommended next steps', createAssessment: 'Save assessment',
    assignment: 'Active assignment', selectAssignment: 'Choose assignment', saved: 'Saved successfully.',
    error: 'Could not load or save learning data.', commaHint: 'Separate items with commas',
    profile: 'Learning profile', assessment: 'Assessment', noAssignments: 'An active assignment is required to add an assessment.',
    privacy: 'Only your family account can view and edit this learner profile.',
  },
  am: {
    parentTitle: 'የተማሪ ፕሮፋይል እና እድገት',
    tutorTitle: 'የችሎታ ግምገማ',
    parentIntro: 'የትምህርት ግቦችን እና የመማር ምርጫዎችን በግል ያስቀምጡ።',
    tutorIntro: 'ለንቁ ምደባ የመጀመሪያ ወይም የእድገት ግምገማ ይመዝግቡ።',
    name: 'የተማሪ ስም', level: 'ክፍል / ደረጃ', subjects: 'ትምህርቶች', goals: 'የትምህርት ግቦች',
    strengths: 'ጠንካራ ጎኖች', focus: 'ማተኮር ያለባቸው', preferences: 'የመማር ምርጫዎች', create: 'ፕሮፋይል ፍጠር',
    save: 'ፕሮፋይል አስቀምጥ', emptyProfiles: 'እስካሁን ፕሮፋይል የለም።', emptyAssessments: 'እስካሁን ግምገማ የለም።',
    subject: 'የተገመገመ ትምህርት', type: 'የግምገማ አይነት', baseline: 'የመጀመሪያ', progress: 'የእድገት ግምገማ',
    score: 'ውጤት (%)', notes: 'የአስጠኚ ማስታወሻ', next: 'ቀጣይ እርምጃዎች', createAssessment: 'ግምገማ አስቀምጥ',
    assignment: 'ንቁ ምደባ', selectAssignment: 'ምደባ ይምረጡ', saved: 'በተሳካ ሁኔታ ተቀምጧል።',
    error: 'የትምህርት መረጃን መጫን ወይም ማስቀመጥ አልተቻለም።',
    commaHint: 'እቃዎችን በኮማ ይለዩ', profile: 'የትምህርት ፕሮፋይል', assessment: 'ግምገማ',
    noAssignments: 'ግምገማ ለመጨመር ንቁ ምደባ ያስፈልጋል።',
    privacy: 'ይህን ፕሮፋይል ማየትና ማስተካከል የሚችለው የቤተሰቡ መለያ ብቻ ነው።',
  },
};

const emptyProfile = {
  learner_name: '', current_level: '', subjects: '', learning_goals: '',
  strengths: '', focus_areas: '', learning_preferences: '',
};

const splitItems = (value) => value.split(',').map((item) => item.trim()).filter(Boolean);
const profileDraft = (profile) => ({
  current_level: profile.current_level || '',
  subjects: (profile.subjects || []).join(', '),
  learning_goals: profile.learning_goals || '',
  strengths: (profile.strengths || []).join(', '),
  focus_areas: (profile.focus_areas || []).join(', '),
  learning_preferences: profile.learning_preferences || '',
});

export default function LearningPanel({ mode = 'parent', lang = 'en', assignments = [] }) {
  const isTutor = mode === 'tutor';
  const t = text[lang] || text.en;
  const [profiles, setProfiles] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [newProfile, setNewProfile] = useState(emptyProfile);
  const [assessment, setAssessment] = useState({ assignment_id: '', subject: '', assessment_type: 'baseline', score_percent: '', strengths: '', focus_areas: '', notes: '', next_steps: '' });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      if (isTutor) {
        // Tutor-created assessment history is available to the family through the parent endpoint.
        // Tutor writes are submitted against the selected assignment below.
      } else {
        const [profileRows, assessmentResult] = await Promise.all([getLearnerProfiles(), getParentAssessments()]);
        setProfiles(profileRows || []);
        setDrafts(Object.fromEntries((profileRows || []).map((profile) => [profile.id, profileDraft(profile)])));
        setAssessments(assessmentResult.assessments || []);
      }
    } catch (err) {
      setError(err.message || t.error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [mode]);

  const createProfile = async (event) => {
    event.preventDefault();
    setBusy(true); setError(''); setNotice('');
    try {
      const saved = await createLearnerProfile({
        learner_name: newProfile.learner_name.trim(),
        current_level: newProfile.current_level.trim(),
        subjects: splitItems(newProfile.subjects),
        learning_goals: newProfile.learning_goals.trim(),
        strengths: splitItems(newProfile.strengths),
        focus_areas: splitItems(newProfile.focus_areas),
        learning_preferences: newProfile.learning_preferences.trim() || null,
      });
      setNewProfile(emptyProfile);
      setNotice(t.saved);
      setProfiles((rows) => [saved, ...rows]);
      setDrafts((rows) => ({ ...rows, [saved.id]: profileDraft(saved) }));
    } catch (err) { setError(err.message || t.error); }
    finally { setBusy(false); }
  };

  const saveProfile = async (profileId) => {
    const draft = drafts[profileId];
    setBusy(true); setError(''); setNotice('');
    try {
      const saved = await updateLearnerProfile(profileId, {
        current_level: draft.current_level.trim(),
        subjects: splitItems(draft.subjects),
        learning_goals: draft.learning_goals.trim(),
        strengths: splitItems(draft.strengths),
        focus_areas: splitItems(draft.focus_areas),
        learning_preferences: draft.learning_preferences.trim() || null,
      });
      setProfiles((rows) => rows.map((item) => item.id === profileId ? saved : item));
      setNotice(t.saved);
    } catch (err) { setError(err.message || t.error); }
    finally { setBusy(false); }
  };

  const submitAssessment = async (event) => {
    event.preventDefault();
    setBusy(true); setError(''); setNotice('');
    try {
      await createTutorAssessment(Number(assessment.assignment_id), {
        subject: assessment.subject.trim(),
        assessment_type: assessment.assessment_type,
        score_percent: assessment.score_percent === '' ? null : Number(assessment.score_percent),
        strengths: splitItems(assessment.strengths),
        focus_areas: splitItems(assessment.focus_areas),
        notes: assessment.notes.trim() || null,
        next_steps: assessment.next_steps.trim() || null,
      });
      setAssessment({ assignment_id: assessment.assignment_id, subject: '', assessment_type: 'progress', score_percent: '', strengths: '', focus_areas: '', notes: '', next_steps: '' });
      setNotice(t.saved);
    } catch (err) { setError(err.message || t.error); }
    finally { setBusy(false); }
  };

  const inputClass = 'mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink';
  const labelClass = 'block text-[10px] font-bold text-muted';

  return (
    <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-citrus/15 p-2 text-citrus">{isTutor ? <ClipboardCheck className="h-4 w-4" /> : <BookOpenCheck className="h-4 w-4" />}</div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-black text-ink">{isTutor ? t.tutorTitle : t.parentTitle}</h3>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">{isTutor ? t.tutorIntro : t.parentIntro}</p>
        </div>
      </div>
      {error && <div role="alert" className="mt-3 flex gap-2 rounded-xl bg-coral/10 p-3 text-[10px] text-coral"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="mt-3 flex gap-2 rounded-xl bg-green/10 p-3 text-[10px] text-green"><CheckCircle2 className="h-4 w-4 shrink-0" />{notice}</div>}

      {isTutor ? (
        <form onSubmit={submitAssessment} className="mt-4 space-y-2 rounded-2xl bg-canvas p-3">
          <label className={labelClass}>{t.assignment}
            <select required value={assessment.assignment_id} onChange={(e) => setAssessment((v) => ({ ...v, assignment_id: e.target.value }))} className={inputClass}>
              <option value="">{t.selectAssignment}</option>
              {assignments.filter((item) => item.status === 'active').map((item) => <option key={item.assignment_id} value={item.assignment_id}>#{item.assignment_id} · {item.student_name_context}</option>)}
            </select>
          </label>
          {!assignments.some((item) => item.status === 'active') && <p className="text-[10px] text-muted">{t.noAssignments}</p>}
          <div className="grid grid-cols-2 gap-2">
            <label className={labelClass}>{t.subject}<input required minLength="2" maxLength="120" value={assessment.subject} onChange={(e) => setAssessment((v) => ({ ...v, subject: e.target.value }))} className={inputClass} /></label>
            <label className={labelClass}>{t.type}
              <select value={assessment.assessment_type} onChange={(e) => setAssessment((v) => ({ ...v, assessment_type: e.target.value }))} className={inputClass}>
                <option value="baseline">{t.baseline}</option><option value="progress">{t.progress}</option>
              </select>
            </label>
          </div>
          <label className={labelClass}>{t.score}<input type="number" min="0" max="100" step="0.1" value={assessment.score_percent} onChange={(e) => setAssessment((v) => ({ ...v, score_percent: e.target.value }))} className={inputClass} /></label>
          <label className={labelClass}>{t.strengths}<input value={assessment.strengths} onChange={(e) => setAssessment((v) => ({ ...v, strengths: e.target.value }))} placeholder={t.commaHint} className={inputClass} /></label>
          <label className={labelClass}>{t.focus}<input value={assessment.focus_areas} onChange={(e) => setAssessment((v) => ({ ...v, focus_areas: e.target.value }))} placeholder={t.commaHint} className={inputClass} /></label>
          <label className={labelClass}>{t.notes}<textarea rows="2" maxLength="5000" value={assessment.notes} onChange={(e) => setAssessment((v) => ({ ...v, notes: e.target.value }))} className={inputClass} /></label>
          <label className={labelClass}>{t.next}<textarea rows="2" maxLength="3000" value={assessment.next_steps} onChange={(e) => setAssessment((v) => ({ ...v, next_steps: e.target.value }))} className={inputClass} /></label>
          <button type="submit" disabled={busy || loading || !assignments.some((item) => item.status === 'active')} className="flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-2.5 text-xs font-black text-paper disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{t.createAssessment}
          </button>
        </form>
      ) : (
        <>
          <form onSubmit={createProfile} className="mt-4 space-y-2 rounded-2xl bg-canvas p-3">
            <p className="text-xs font-black text-ink">{t.profile}</p>
            <label className={labelClass}>{t.name}<input required minLength="2" maxLength="150" value={newProfile.learner_name} onChange={(e) => setNewProfile((v) => ({ ...v, learner_name: e.target.value }))} className={inputClass} /></label>
            <label className={labelClass}>{t.level}<input required minLength="2" maxLength="100" value={newProfile.current_level} onChange={(e) => setNewProfile((v) => ({ ...v, current_level: e.target.value }))} className={inputClass} /></label>
            <label className={labelClass}>{t.subjects}<input required value={newProfile.subjects} onChange={(e) => setNewProfile((v) => ({ ...v, subjects: e.target.value }))} placeholder={t.commaHint} className={inputClass} /></label>
            <label className={labelClass}>{t.goals}<textarea required minLength="3" maxLength="3000" rows="2" value={newProfile.learning_goals} onChange={(e) => setNewProfile((v) => ({ ...v, learning_goals: e.target.value }))} className={inputClass} /></label>
            <label className={labelClass}>{t.strengths}<input value={newProfile.strengths} onChange={(e) => setNewProfile((v) => ({ ...v, strengths: e.target.value }))} placeholder={t.commaHint} className={inputClass} /></label>
            <label className={labelClass}>{t.focus}<input value={newProfile.focus_areas} onChange={(e) => setNewProfile((v) => ({ ...v, focus_areas: e.target.value }))} placeholder={t.commaHint} className={inputClass} /></label>
            <label className={labelClass}>{t.preferences}<textarea rows="2" maxLength="2000" value={newProfile.learning_preferences} onChange={(e) => setNewProfile((v) => ({ ...v, learning_preferences: e.target.value }))} className={inputClass} /></label>
            <button type="submit" disabled={busy || loading} className="flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-2.5 text-xs font-black text-paper disabled:opacity-50">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{t.create}
            </button>
          </form>

          <div className="mt-4 space-y-3">
            {loading ? <div className="flex justify-center p-4"><Loader2 className="h-5 w-5 animate-spin text-pine" /></div> :
              profiles.length ? profiles.map((profile) => {
                const draft = drafts[profile.id] || profileDraft(profile);
                return (
                  <article key={profile.id} className="rounded-2xl border border-line p-3">
                    <h4 className="text-xs font-black text-ink">{profile.learner_name}</h4>
                    <p className="mt-1 text-[9px] text-muted">{t.privacy}</p>
                    <div className="mt-3 space-y-2">
                      {[
                        ['current_level', t.level, 'text'],
                        ['subjects', t.subjects, 'text'],
                        ['learning_goals', t.goals, 'textarea'],
                        ['strengths', t.strengths, 'text'],
                        ['focus_areas', t.focus, 'text'],
                        ['learning_preferences', t.preferences, 'textarea'],
                      ].map(([field, label, kind]) => (
                        <label key={field} className={labelClass}>{label}
                          {kind === 'textarea' ? <textarea rows="2" value={draft[field] || ''} onChange={(e) => setDrafts((v) => ({ ...v, [profile.id]: { ...v[profile.id], [field]: e.target.value } }))} className={inputClass} /> :
                            <input value={draft[field] || ''} onChange={(e) => setDrafts((v) => ({ ...v, [profile.id]: { ...v[profile.id], [field]: e.target.value } }))} className={inputClass} />}
                        </label>
                      ))}
                      <button type="button" onClick={() => saveProfile(profile.id)} disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl border border-line py-2.5 text-xs font-black text-pine disabled:opacity-50">
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t.save}
                      </button>
                    </div>
                  </article>
                );
              }) : <div className="rounded-2xl bg-canvas p-4 text-center text-[10px] text-muted">{t.emptyProfiles}</div>}
          </div>

          <div className="mt-4">
            <h4 className="mb-2 text-xs font-black text-ink">{t.assessment}</h4>
            {loading ? <div className="flex justify-center p-4"><Loader2 className="h-5 w-5 animate-spin text-pine" /></div> :
              assessments.length ? <div className="space-y-2">{assessments.map((item) => (
                <article key={item.id} className="rounded-2xl border border-line p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div><h5 className="text-xs font-black text-ink">{item.learner_name} · {item.subject}</h5><p className="mt-1 text-[9px] text-muted">{item.assessment_type === 'baseline' ? t.baseline : t.progress} · {new Date(item.assessed_at).toLocaleDateString()}</p></div>
                    {item.score_percent !== null && item.score_percent !== undefined && <span className="rounded-xl bg-pine/10 px-2 py-1 text-xs font-black text-pine">{item.score_percent}%</span>}
                  </div>
                  {item.strengths?.length > 0 && <p className="mt-2 text-[10px] text-muted"><strong>{t.strengths}: </strong>{item.strengths.join(', ')}</p>}
                  {item.focus_areas?.length > 0 && <p className="mt-1 text-[10px] text-muted"><strong>{t.focus}: </strong>{item.focus_areas.join(', ')}</p>}
                  {item.notes && <p className="mt-2 whitespace-pre-wrap text-[10px] text-ink">{item.notes}</p>}
                  {item.next_steps && <p className="mt-2 rounded-xl bg-canvas p-2 text-[10px] text-ink"><strong>{t.next}: </strong>{item.next_steps}</p>}
                </article>
              ))}</div> : <div className="rounded-2xl bg-canvas p-4 text-center text-[10px] text-muted">{t.emptyAssessments}</div>}
          </div>
        </>
      )}
    </section>
  );
}
