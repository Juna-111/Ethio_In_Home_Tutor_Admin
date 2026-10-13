import React, { useEffect, useRef, useState } from 'react';
import { AlertCircle, BookOpen, CheckCircle2, Clock3, Loader2, Play, RotateCcw, Send } from 'lucide-react';
import { saveMockExamAnswers, startMockExam, submitMockExam } from '../services/api';

const labels = {
  en: {
    title: 'Exam practice & mock tests',
    intro: 'Practise curriculum topics or start a timed mock exam. Answer keys appear only after submission.',
    subject: 'Subject', topic: 'Topic (optional)', grade: 'Grade / level (optional)',
    count: 'Questions', minutes: 'Time (minutes)', start: 'Start timed mock exam',
    noQuestions: 'No questions are available for these filters yet. Ask the admin team to add curriculum-aligned questions.',
    empty: 'Choose a subject and start an exam to begin practising.',
    submit: 'Submit and review', question: 'Question', saved: 'Answers saved',
    saveError: 'Your answer could not be saved. Check your connection and try again.',
    score: 'Your score', correct: 'correct', expired: 'Time expired', review: 'Answer review',
    correctAnswer: 'Correct answer', yourAnswer: 'Your answer', unanswered: 'Not answered',
    explanation: 'Explanation', restart: 'Start another exam', loadError: 'Could not start the mock exam.',
    timer: 'Time remaining', saving: 'Saving answers…', submitting: 'Scoring your attempt…',
  },
  am: {
    title: 'የፈተና ልምምድ እና የሙከራ ፈተና',
    intro: 'በርዕሶች ላይ ይለማመዱ ወይም በጊዜ የተገደበ ፈተና ይጀምሩ።',
    subject: 'ትምህርት', topic: 'ርዕስ (አማራጭ)', grade: 'ክፍል / ደረጃ (አማራጭ)',
    count: 'ጥያቄዎች', minutes: 'ጊዜ (ደቂቃ)', start: 'የሙከራ ፈተና ጀምር',
    noQuestions: 'ለእነዚህ ማጣሪያዎች ጥያቄ የለም።', empty: 'ትምህርት ይምረጡና ፈተና ይጀምሩ።',
    submit: 'አስገባ እና ውጤት እይ', question: 'ጥያቄ', saved: 'መልሶች ተቀምጠዋል',
    saveError: 'መልሱን ማስቀመጥ አልተቻለም።', score: 'ውጤት', correct: 'ትክክል',
    expired: 'ጊዜ አልቋል', review: 'የመልስ ግምገማ', correctAnswer: 'ትክክለኛ መልስ',
    yourAnswer: 'መልስዎ', unanswered: 'አልተመለሰም', explanation: 'ማብራሪያ',
    restart: 'ሌላ ፈተና ጀምር', loadError: 'ፈተናውን መጀመር አልተቻለም።',
    timer: 'የቀረ ጊዜ', saving: 'መልሶች በመቀመጥ ላይ…', submitting: 'ውጤት በማስላት ላይ…',
  },
};

function formatRemaining(seconds) {
  const value = Math.max(0, seconds);
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

export default function ExamPracticePanel({ lang = 'en' }) {
  const t = labels[lang] || labels.en;
  const [form, setForm] = useState({ subject: '', topic: '', grade_level: '', question_count: '10', time_limit_minutes: '20' });
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const saveSequence = useRef(0);

  useEffect(() => {
    if (!attempt || result) return undefined;
    const updateClock = () => setSecondsLeft(Math.max(0, Math.ceil((new Date(attempt.expires_at).getTime() - Date.now()) / 1000)));
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, [attempt, result]);

  const start = async (event) => {
    event.preventDefault();
    setBusy(true); setError(''); setNotice(''); setResult(null); setAttempt(null); setAnswers({});
    try {
      const data = await startMockExam({
        subject: form.subject.trim(),
        topic: form.topic.trim() || null,
        grade_level: form.grade_level.trim() || null,
        question_count: Number(form.question_count),
        time_limit_minutes: Number(form.time_limit_minutes),
      });
      setAttempt(data);
      setSecondsLeft(data.time_limit_seconds);
    } catch (err) {
      setError(err.message || t.loadError);
    } finally { setBusy(false); }
  };

  const chooseAnswer = async (questionId, optionIndex) => {
    const next = { ...answers, [String(questionId)]: optionIndex };
    setAnswers(next);
    setSaving(true); setError(''); setNotice('');
    const sequence = ++saveSequence.current;
    try {
      await saveMockExamAnswers(attempt.attempt_id, next);
      if (sequence === saveSequence.current) setNotice(t.saved);
    } catch (err) {
      if (sequence === saveSequence.current) setError(err.message || t.saveError);
    } finally {
      if (sequence === saveSequence.current) setSaving(false);
    }
  };

  const submit = async () => {
    if (!attempt || busy || result) return;
    setBusy(true); setError(''); setNotice('');
    try {
      // Save the complete local answer set before asking the server to score it.
      if (Object.keys(answers).length) await saveMockExamAnswers(attempt.attempt_id, answers);
      const data = await submitMockExam(attempt.attempt_id);
      setResult(data);
    } catch (err) {
      setError(err.message || t.loadError);
    } finally { setBusy(false); }
  };

  const reset = () => {
    setAttempt(null); setAnswers({}); setResult(null); setError(''); setNotice('');
  };

  return (
    <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-coral/10 p-2 text-coral"><BookOpen className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-black text-ink">{t.title}</h3>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">{t.intro}</p>
        </div>
      </div>
      {error && <div role="alert" className="mt-3 flex gap-2 rounded-xl bg-coral/10 p-3 text-[10px] text-coral"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="mt-3 flex gap-2 rounded-xl bg-green/10 p-3 text-[10px] text-green"><CheckCircle2 className="h-4 w-4 shrink-0" />{saving ? t.saving : notice}</div>}

      {!attempt && !result && (
        <form onSubmit={start} className="mt-4 space-y-2 rounded-2xl bg-canvas p-3">
          <label className="block text-[10px] font-bold text-muted">{t.subject}
            <input required minLength="2" maxLength="120" value={form.subject} onChange={(e) => setForm((v) => ({ ...v, subject: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" placeholder="Mathematics" />
          </label>
          <label className="block text-[10px] font-bold text-muted">{t.topic}
            <input maxLength="200" value={form.topic} onChange={(e) => setForm((v) => ({ ...v, topic: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" />
          </label>
          <label className="block text-[10px] font-bold text-muted">{t.grade}
            <input maxLength="100" value={form.grade_level} onChange={(e) => setForm((v) => ({ ...v, grade_level: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" placeholder="Grade 8" />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-[10px] font-bold text-muted">{t.count}
              <input type="number" min="1" max="50" value={form.question_count} onChange={(e) => setForm((v) => ({ ...v, question_count: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" />
            </label>
            <label className="block text-[10px] font-bold text-muted">{t.minutes}
              <input type="number" min="1" max="180" value={form.time_limit_minutes} onChange={(e) => setForm((v) => ({ ...v, time_limit_minutes: e.target.value }))} className="mt-1 w-full rounded-xl border border-line bg-paper p-2.5 text-xs text-ink" />
            </label>
          </div>
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-pine py-2.5 text-xs font-black text-paper disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{t.start}
          </button>
        </form>
      )}

      {attempt && !result && (
        <div className="mt-4 space-y-3">
          <div className="sticky top-2 z-10 flex items-center justify-between gap-3 rounded-2xl bg-ink p-3 text-paper shadow-lg">
            <div><p className="text-[9px] font-bold text-paper/70">{attempt.subject}{attempt.topic ? ` · ${attempt.topic}` : ''}</p><p className="text-xs font-black">{t.timer}</p></div>
            <div className={`flex items-center gap-1 rounded-xl px-2.5 py-1.5 font-mono text-sm font-black ${secondsLeft <= 60 ? 'bg-coral text-white' : 'bg-white/10 text-paper'}`}><Clock3 className="h-4 w-4" />{formatRemaining(secondsLeft)}</div>
          </div>
          {attempt.questions.map((question, index) => (
            <article key={question.id} className="rounded-2xl border border-line p-3">
              <p className="text-[9px] font-black uppercase tracking-wider text-pine">{t.question} {index + 1} / {attempt.questions.length}</p>
              <h4 className="mt-2 text-xs font-bold leading-relaxed text-ink">{question.prompt}</h4>
              <div className="mt-3 space-y-2">
                {question.options.map((option, optionIndex) => (
                  <label key={optionIndex} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-xs ${answers[String(question.id)] === optionIndex ? 'border-pine bg-pine/10 text-ink' : 'border-line text-muted'} ${secondsLeft <= 0 ? 'opacity-60' : ''}`}>
                    <input type="radio" name={`question-${question.id}`} value={optionIndex} checked={answers[String(question.id)] === optionIndex} disabled={secondsLeft <= 0 || busy} onChange={() => chooseAnswer(question.id, optionIndex)} className="mt-0.5 accent-[var(--pine)]" />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </article>
          ))}
          {secondsLeft <= 0 && <p role="alert" className="rounded-xl bg-coral/10 p-3 text-xs font-bold text-coral">{t.expired}. Submit to score your saved answers.</p>}
          <button type="button" onClick={submit} disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-coral py-3 text-xs font-black text-white disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{busy ? t.submitting : t.submit}
          </button>
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="rounded-2xl bg-pine p-4 text-center text-paper">
            <p className="text-[10px] font-bold text-paper/70">{t.score}</p>
            <p className="mt-1 text-3xl font-black">{result.score_percent}%</p>
            <p className="mt-1 text-xs">{result.correct_count} / {result.question_count} {t.correct}</p>
            {result.expired && <p className="mt-2 text-[10px] font-bold text-citrus">{t.expired}</p>}
          </div>
          <h4 className="text-xs font-black text-ink">{t.review}</h4>
          {result.results.map((item, index) => (
            <article key={item.question_id} className="rounded-2xl border border-line p-3">
              <div className="flex items-start gap-2">
                {item.is_correct ? <CheckCircle2 className="h-4 w-4 shrink-0 text-green" /> : <AlertCircle className="h-4 w-4 shrink-0 text-coral" />}
                <div className="min-w-0"><p className="text-xs font-bold text-ink">{index + 1}. {item.prompt}</p>
                  <p className="mt-2 text-[10px] text-muted">{t.yourAnswer}: {item.selected_option_index === null || item.selected_option_index === undefined ? t.unanswered : item.options[item.selected_option_index]}</p>
                  <p className="mt-1 text-[10px] font-bold text-green">{t.correctAnswer}: {item.options[item.correct_option_index]}</p>
                  {item.explanation && <p className="mt-2 text-[10px] leading-relaxed text-muted">{t.explanation}: {item.explanation}</p>}
                </div>
              </div>
            </article>
          ))}
          <button type="button" onClick={reset} className="flex w-full items-center justify-center gap-2 rounded-xl border border-line py-2.5 text-xs font-black text-pine"><RotateCcw className="h-4 w-4" />{t.restart}</button>
        </div>
      )}
      {!attempt && !result && <p className="mt-3 rounded-xl bg-canvas p-3 text-center text-[10px] text-muted">{t.empty}</p>}
    </section>
  );
}
