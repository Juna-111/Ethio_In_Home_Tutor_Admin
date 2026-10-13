import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, BookOpenCheck, CheckCircle2, Loader2, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import { createAdminPracticeQuestion, getAdminPracticeQuestions, setAdminPracticeQuestionActive } from '../services/api';

const initialForm = {
  subject: '', grade_level: '', topic: '', difficulty: '3', prompt: '',
  options: '', correct_option_index: '', explanation: '',
};

export default function QuestionBankManager() {
  const [form, setForm] = useState(initialForm);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const options = useMemo(() => form.options.split('\n').map((value) => value.trim()).filter(Boolean), [form.options]);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const result = await getAdminPracticeQuestions();
      setQuestions(result.questions || []);
    } catch (err) {
      setError(err.message || 'Question bank could not be loaded.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const create = async (event) => {
    event.preventDefault();
    setBusy(true); setError(''); setNotice('');
    try {
      await createAdminPracticeQuestion({
        subject: form.subject.trim(),
        grade_level: form.grade_level.trim(),
        topic: form.topic.trim(),
        difficulty: Number(form.difficulty),
        prompt: form.prompt.trim(),
        options,
        correct_option_index: Number(form.correct_option_index),
        explanation: form.explanation.trim() || null,
      });
      setForm(initialForm());
      setNotice('Question added to the bank.');
      await load();
    } catch (err) {
      setError(err.message || 'Question could not be saved.');
    } finally { setBusy(false); }
  };

  const toggle = async (question) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await setAdminPracticeQuestionActive(question.id, !question.is_active);
      setQuestions((items) => items.map((item) => item.id === question.id ? { ...item, is_active: !item.is_active } : item));
      setNotice(question.is_active ? 'Question hidden from student practice.' : 'Question is available for student practice.');
    } catch (err) {
      setError(err.message || 'Question status could not be updated.');
    } finally { setBusy(false); }
  };

  const inputClass = 'mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink';
  const labelClass = 'block text-[10px] font-bold text-muted';

  return (
    <section className="space-y-4">
      <header className="rounded-3xl bg-gradient-to-br from-pine via-pine to-ink p-5 text-paper shadow-lg">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/10 p-3 text-citrus"><BookOpenCheck className="h-5 w-5" /></div>
          <div><p className="text-[9px] font-black uppercase tracking-[0.18em] text-paper/60">MentorLink · Admin</p><h1 className="mt-1 text-xl font-black">Exam question bank</h1><p className="mt-1 text-[10px] leading-relaxed text-paper/70">Create curriculum-aligned questions and control which items appear in student mock exams.</p></div>
          <button type="button" onClick={load} aria-label="Refresh question bank" className="ml-auto rounded-xl border border-white/10 bg-white/10 p-2"><RefreshCw className="h-4 w-4" /></button>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-white/5 p-2.5"><p className="text-lg font-black text-citrus">{questions.length}</p><p className="text-[9px] text-paper/65">Total questions</p></div>
          <div className="rounded-xl bg-white/5 p-2.5"><p className="text-lg font-black text-citrus">{questions.filter((q) => q.is_active).length}</p><p className="text-[9px] text-paper/65">Active</p></div>
          <div className="rounded-xl bg-white/5 p-2.5"><p className="text-lg font-black text-citrus">{new Set(questions.map((q) => q.subject)).size}</p><p className="text-[9px] text-paper/65">Subjects</p></div>
        </div>
      </header>

      {error && <div role="alert" className="flex gap-2 rounded-2xl border border-coral/20 bg-coral/10 p-3 text-xs text-coral"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="flex gap-2 rounded-2xl bg-green/10 p-3 text-xs text-green"><CheckCircle2 className="h-4 w-4 shrink-0" />{notice}</div>}

      <form onSubmit={create} className="space-y-3 rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-center gap-2"><Plus className="h-4 w-4 text-pine" /><h2 className="text-sm font-black text-ink">Add a question</h2></div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label className={labelClass}>Subject<input required minLength="2" maxLength="120" value={form.subject} onChange={(e) => setForm((v) => ({ ...v, subject: e.target.value }))} className={inputClass} /></label>
          <label className={labelClass}>Grade / level<input required minLength="2" maxLength="100" value={form.grade_level} onChange={(e) => setForm((v) => ({ ...v, grade_level: e.target.value }))} className={inputClass} /></label>
          <label className={labelClass}>Topic / chapter<input required minLength="2" maxLength="200" value={form.topic} onChange={(e) => setForm((v) => ({ ...v, topic: e.target.value }))} className={inputClass} /></label>
          <label className={labelClass}>Difficulty (1 easy · 5 hard)<select value={form.difficulty} onChange={(e) => setForm((v) => ({ ...v, difficulty: e.target.value }))} className={inputClass}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
        </div>
        <label className={labelClass}>Question prompt<textarea required minLength="3" maxLength="5000" rows="3" value={form.prompt} onChange={(e) => setForm((v) => ({ ...v, prompt: e.target.value }))} className={inputClass} /></label>
        <label className={labelClass}>Answer options (one per line)
          <textarea required rows="4" value={form.options} onChange={(e) => setForm((v) => ({ ...v, options: e.target.value, correct_option_index: '' }))} className={inputClass} placeholder={'Option A\nOption B\nOption C\nOption D'} />
        </label>
        <label className={labelClass}>Correct answer<select required value={form.correct_option_index} onChange={(e) => setForm((v) => ({ ...v, correct_option_index: e.target.value }))} className={inputClass}>
          <option value="">Choose the correct option</option>{options.map((option, index) => <option key={index} value={index}>{String.fromCharCode(65 + index)} · {option}</option>)}
        </select></label>
        <label className={labelClass}>Explanation (shown after submission)<textarea rows="2" maxLength="3000" value={form.explanation} onChange={(e) => setForm((v) => ({ ...v, explanation: e.target.value }))} className={inputClass} /></label>
        <button type="submit" disabled={busy || options.length < 2 || form.correct_option_index === ''} className="flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-3 text-xs font-black text-paper disabled:opacity-50">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Save question
        </button>
      </form>

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2"><div><h2 className="text-sm font-black text-ink">Question library</h2><p className="mt-1 text-[10px] text-muted">Answer keys are visible only in the protected admin workspace.</p></div>{loading && <Loader2 className="h-4 w-4 animate-spin text-pine" />}</div>
        <div className="mt-3 space-y-2">
          {questions.map((question) => (
            <article key={question.id} className="rounded-2xl border border-line p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0"><p className="text-[9px] font-black uppercase tracking-wider text-pine">{question.subject} · {question.grade_level} · {question.topic}</p><h3 className="mt-1 text-xs font-black leading-relaxed text-ink">{question.prompt}</h3></div>
                <span className={`shrink-0 rounded-full px-2 py-1 text-[8px] font-black ${question.is_active ? 'bg-green/10 text-green' : 'bg-coral/10 text-coral'}`}>{question.is_active ? 'Active' : 'Hidden'}</span>
              </div>
              <ol className="mt-2 space-y-1 text-[10px] text-muted">{question.options.map((option, index) => <li key={index} className={index === question.correct_option_index ? 'font-black text-green' : ''}>{String.fromCharCode(65 + index)}. {option}{index === question.correct_option_index ? ' ✓' : ''}</li>)}</ol>
              {question.explanation && <p className="mt-2 rounded-xl bg-canvas p-2 text-[10px] text-muted">{question.explanation}</p>}
              <button type="button" disabled={busy} onClick={() => toggle(question)} className="mt-3 rounded-xl border border-line px-3 py-2 text-[10px] font-black text-pine disabled:opacity-50">{question.is_active ? 'Hide from students' : 'Publish to students'}</button>
            </article>
          ))}
          {!loading && !questions.length && <div className="rounded-2xl bg-canvas p-5 text-center text-xs text-muted">No questions yet. Add the first curriculum-aligned question above.</div>}
        </div>
      </section>
    </section>
  );
}
