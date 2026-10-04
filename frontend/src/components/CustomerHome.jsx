import React from 'react';
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  BriefcaseBusiness,
  GraduationCap,
  Home,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from 'lucide-react';

function BrandMark({ large = false }) {
  return (
    <div
      className={`relative flex items-center justify-center rounded-2xl border border-citrus/40 bg-white/10 shadow-inner ${large ? 'h-16 w-16' : 'h-10 w-10'}`}
      aria-hidden="true"
    >
      <Home className={large ? 'absolute h-8 w-8 text-citrus' : 'absolute h-5 w-5 text-citrus'} strokeWidth={1.8} />
      <BookOpen className={large ? 'absolute h-5 w-5 translate-y-1 text-paper' : 'absolute h-3.5 w-3.5 translate-y-0.5 text-paper'} strokeWidth={2.2} />
    </div>
  );
}

export default function CustomerHome({ user, lang, onSelectTab }) {
  const isAm = lang === 'am';
  const firstName = user?.first_name || '';

  const choose = (tab) => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light');
    } catch (_) {}
    onSelectTab(tab);
  };

  return (
    <main className="flex-1 px-4 pb-10">
      {/* Hero / brand promise */}
      <section className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-pine via-pine to-ink px-5 py-7 text-paper shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-citrus/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-14 -left-10 h-32 w-32 rounded-full bg-green/15 blur-2xl" />

        <div className="relative">
          <div className="mb-5 flex items-center gap-3">
            <BrandMark large />
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-citrus">
                Ethio In-Home Tutor
              </p>
              <p className="mt-1 text-xs font-medium text-paper/70">
                {isAm ? 'የተማሪና የአስጠኚ የታመነ መድረክ' : 'A trusted home for families & tutors'}
              </p>
            </div>
          </div>

          <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-[10px] font-bold text-paper/90">
            <Sparkles className="h-3 w-3 text-citrus" />
            {isAm ? 'የተሻለ የቤት ውስጥ ትምህርት' : 'Personalized in-home learning'}
          </div>

          <h1 className="max-w-[330px] text-2xl font-black leading-tight tracking-tight sm:text-3xl">
            {firstName
              ? (isAm ? `እንኳን ደህና መጡ, ${firstName}!` : `Welcome, ${firstName}.`)
              : (isAm ? 'ለትምህርት ትክክለኛ ሰው እናገናኝዎታለን።' : 'The right tutor. The right student. One trusted place.')}
          </h1>
          <p className="mt-3 max-w-[330px] text-sm leading-relaxed text-paper/75">
            {isAm
              ? 'ለልጅዎ ተስማሚ አስጠኚ ያግኙ ወይም እንደ አስጠኚ ወደ የታመነ የማስተማር ማህበረሰብ ይቀላቀሉ።'
              : 'Families can request a tutor in minutes. Qualified educators can build a professional teaching profile and manage their opportunities.'}
          </p>

          <div className="mt-5 grid grid-cols-3 gap-2">
            {[
              { icon: ShieldCheck, label: isAm ? 'የታመነ' : 'Trusted' },
              { icon: UsersRound, label: isAm ? 'ለቤተሰብ' : 'Family-first' },
              { icon: BadgeCheck, label: isAm ? 'የተረጋገጠ' : 'Verified' },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="rounded-xl border border-white/10 bg-white/5 px-2 py-2 text-center">
                <Icon className="mx-auto mb-1 h-3.5 w-3.5 text-citrus" />
                <span className="text-[9px] font-bold text-paper/75">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Role gateway */}
      <section className="mt-5">
        <div className="mb-3">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-citrus">
            {isAm ? 'መንገድዎን ይምረጡ' : 'Choose your path'}
          </p>
          <h2 className="mt-1 text-lg font-black text-ink">
            {isAm ? 'የትኛው ክፍል ይፈልጋሉ?' : 'What brings you here?'}
          </h2>
        </div>

        <div className="space-y-3">
          <button
            type="button"
            onClick={() => choose('parent')}
            className="group w-full rounded-2xl border border-line bg-paper p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-pine/30 hover:shadow-md active:scale-[0.99]"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine/10 text-pine">
                <UsersRound className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-black text-ink">
                    {isAm ? 'ወላጅ / ቤተሰብ' : 'I’m a Parent / Family'}
                  </h3>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-1 group-hover:text-pine" />
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {isAm
                    ? 'አስጠኚ ይፈልጉ፣ ጥያቄዎን ይከታተሉ እና የትምህርት ጉዞዎን ያስተዳድሩ።'
                    : 'Find a suitable tutor, submit a learning request, and manage your family portal.'}
                </p>
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => choose('tutor')}
            className="group w-full rounded-2xl border border-citrus/35 bg-gradient-to-br from-citrus/10 to-paper p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-citrus/60 hover:shadow-md active:scale-[0.99]"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-citrus/15 text-citrus">
                <GraduationCap className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-black text-ink">
                    {isAm ? 'አስጠኚ / አስተማሪ' : 'I’m a Tutor / Educator'}
                  </h3>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-1 group-hover:text-pine" />
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {isAm
                    ? 'ፕሮፋይልዎን ይገንቡ፣ የማስተማር እድሎችን ያግኙ እና ስራዎን ያስተዳድሩ።'
                    : 'Join the tutor network, build your verified profile, and manage your teaching work.'}
                </p>
              </div>
            </div>
          </button>
        </div>
      </section>

      {/* Small promotion */}
      <section className="mt-5 overflow-hidden rounded-2xl border border-line bg-white/70 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-pine/10 p-2 text-pine">
            <BriefcaseBusiness className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-black text-ink">
              {isAm ? 'አንድ መድረክ፣ ብዙ እድሎች' : 'Your tutoring journey, all in one place'}
            </h3>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">
              {isAm
                ? 'ዛሬ በመመዝገብ ይጀምሩ፤ የወደፊት የጊዜ ሰሌዳ፣ ክፍያ፣ ግምገማ እና የትምህርት መሳሪያዎች ወደ የግል ፖርታልዎ ይጨመራሉ።'
                : 'Start today. Scheduling, payments, reviews, learning progress, and future tools can grow inside your private role-based portal.'}
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mt-5 rounded-2xl border border-line bg-paper p-4">
        <div className="mb-3 flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-pine" />
          <h3 className="text-xs font-black text-ink">{isAm ? 'እንዴት ይሰራል?' : 'How it works'}</h3>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { n: '01', title: isAm ? 'ይምረጡ' : 'Choose', text: isAm ? 'ወላጅ ወይም አስጠኚ' : 'Parent or tutor' },
            { n: '02', title: isAm ? 'ይጀምሩ' : 'Start', text: isAm ? 'ቀላል ምዝገባ' : 'Simple onboarding' },
            { n: '03', title: isAm ? 'ያስተዳድሩ' : 'Manage', text: isAm ? 'በፖርታልዎ' : 'Inside your portal' },
          ].map((step) => (
            <div key={step.n} className="rounded-xl bg-[#f1f3ef] p-2.5">
              <span className="text-[9px] font-black text-citrus">{step.n}</span>
              <p className="mt-1 text-[10px] font-black text-ink">{step.title}</p>
              <p className="mt-0.5 text-[9px] leading-relaxed text-muted">{step.text}</p>
            </div>
          ))}
        </div>
      </section>

      <p className="mt-5 text-center text-[9px] font-semibold tracking-wide text-muted">
        {isAm ? 'የተሰራ ለኢትዮጵያዊ ቤተሰቦችና አስጠኚዎች' : 'Built for Ethiopian families and educators'}
      </p>
    </main>
  );
}
