import React from 'react';
import { BookOpen, User, Globe } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function Header({ user, lang, onToggleLang }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  return (
    <header className="bg-gradient-to-r from-pine to-ink text-paper p-4 sm:p-5 rounded-b-3xl shadow-lg border-b-2 border-citrus/40 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 sm:w-11 sm:h-11 bg-white/15 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/20 shadow-inner">
            <BookOpen className="w-5 h-5 sm:w-6 sm:h-6 text-paper" />
          </div>
          <div>
            <h1 className="text-lg sm:text-xl font-bold tracking-tight text-paper">{t.appTitle}</h1>
            <p className="text-[11px] sm:text-xs text-paper/80 font-medium">{t.appSubtitle}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Language Switcher */}
          <button
            type="button"
            onClick={onToggleLang}
            className="flex items-center space-x-1 bg-white/15 hover:bg-white/25 backdrop-blur-sm px-2.5 py-1.5 rounded-full border border-white/20 text-xs font-bold transition active:scale-95 cursor-pointer shadow-inner"
            title="Switch Language / ቋንቋ ቀይር"
          >
            <Globe className="w-3.5 h-3.5 text-paper/80" />
            <span className={lang === 'en' ? 'text-paper font-black' : 'text-paper/70'}>EN</span>
            <span className="text-white/40 text-[10px]">|</span>
            <span className={lang === 'am' ? 'text-paper font-black' : 'text-paper/70'}>አማ</span>
          </button>

          {user ? (
            <div className="hidden sm:flex items-center space-x-1.5 bg-white/10 backdrop-blur-sm px-2.5 py-1.5 rounded-full border border-white/15 text-xs font-medium text-paper">
              <User className="w-3.5 h-3.5 text-paper/80" />
              <span className="truncate max-w-[80px]">{user.first_name || user.username}</span>
            </div>
          ) : (
            <div className="hidden sm:block bg-white/10 px-2 py-1 rounded-full text-[10px] text-paper/80 font-medium border border-white/15">
              {t.webPreview}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
