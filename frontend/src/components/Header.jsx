import React from 'react';
import { ArrowLeft, Globe, User } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

function BrandMark() {
  return (
    <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-citrus/40 bg-white/10 shadow-inner">
      <span className="absolute text-sm font-black text-citrus">E</span>
      <span className="absolute bottom-1.5 h-px w-5 bg-paper/80" />
    </div>
  );
}

export default function Header({ user, lang, onToggleLanguage, showHome, onHome }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  return (
    <header className="sticky top-0 z-40 mb-4 border-b-2 border-citrus/50 bg-gradient-to-r from-pine via-pine to-ink p-4 text-paper shadow-lg sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={showHome ? onHome : undefined}
          className={`flex min-w-0 items-center gap-3 text-left ${showHome ? 'cursor-pointer' : 'cursor-default'}`}
          aria-label={showHome ? 'Back to Ethio In-Home Tutor home' : 'Ethio In-Home Tutor'}
        >
          {showHome ? (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/10">
              <ArrowLeft className="h-4 w-4 text-paper" />
            </span>
          ) : (
            <BrandMark />
          )}
          <span className="min-w-0">
            <span className="block truncate text-sm font-black tracking-tight text-paper sm:text-base">
              {t.appTitle}
            </span>
            <span className="block truncate text-[9px] font-bold uppercase tracking-[0.16em] text-paper/60">
              {showHome ? (lang === 'am' ? 'ወደ መነሻ ይመለሱ' : 'Back to home') : t.appSubtitle}
            </span>
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onToggleLanguage}
            className="flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-2.5 py-1.5 text-[10px] font-bold shadow-inner transition hover:bg-white/20 active:scale-95"
            title="Switch Language / ቋንቋ ቀይር"
          >
            <Globe className="h-3.5 w-3.5 text-paper/75" />
            <span className={lang === 'en' ? 'font-black text-paper' : 'text-paper/55'}>EN</span>
            <span className="text-white/30">|</span>
            <span className={lang === 'am' ? 'font-black text-paper' : 'text-paper/55'}>አማ</span>
          </button>

          {user ? (
            <div className="flex max-w-[92px] items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-2.5 py-1.5 text-[10px] font-medium text-paper">
              <User className="h-3.5 w-3.5 shrink-0 text-paper/75" />
              <span className="truncate">{user.first_name || user.username}</span>
            </div>
          ) : (
            <span className="rounded-full border border-white/15 bg-white/10 px-2 py-1 text-[9px] font-bold text-paper/65">
              {t.webPreview}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
