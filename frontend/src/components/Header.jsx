import React from 'react';
import { ArrowLeft, Globe, User, Wifi, WifiOff } from 'lucide-react';
import BrandMark from './BrandMark';
import { TRANSLATIONS } from '../constants/translations';


export default function Header({ user, lang, onToggleLanguage, lowDataMode, onToggleLowData, showHome, onHome }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  return (
    <header className="sticky top-0 z-40 mb-4 border-b-2 border-citrus/50 bg-gradient-to-r from-pine via-pine to-ink p-4 text-paper shadow-lg sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={showHome ? onHome : undefined}
          className={`flex min-w-0 items-center gap-3 text-left ${showHome ? 'cursor-pointer' : 'cursor-default'}`}
          aria-label={showHome ? 'Back to MentorLink home' : 'MentorLink'}
        >
          {showHome ? (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/10">
              <ArrowLeft className="h-4 w-4 text-paper" />
            </span>
          ) : (
            <BrandMark size="small" />
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
            onClick={onToggleLowData}
            aria-pressed={Boolean(lowDataMode)}
            aria-label={lowDataMode ? (lang === 'am' ? 'ዝቅተኛ ዳታ አጥፋ' : 'Disable low-data mode') : (lang === 'am' ? 'ዝቅተኛ ዳታ አብራ' : 'Enable low-data mode')}
            title={lowDataMode ? (lang === 'am' ? 'ዝቅተኛ ዳታ ነቅቷል' : 'Low-data mode enabled') : (lang === 'am' ? 'ዝቅተኛ ዳታ አንቃ' : 'Enable low-data mode')}
            className={`flex items-center justify-center rounded-full border px-2 py-1.5 text-[10px] font-bold transition ${lowDataMode ? 'border-citrus bg-citrus/20 text-paper' : 'border-white/20 bg-white/10 text-paper'}`}
          >
            {lowDataMode ? <WifiOff className="h-3.5 w-3.5" /> : <Wifi className="h-3.5 w-3.5" />}
          </button>

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
