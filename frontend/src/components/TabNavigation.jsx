import React from 'react';
import { ArrowLeft, Briefcase, ClipboardList, GraduationCap, Search } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function TabNavigation({ activeTab, onSelectTab, lang }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;
  const isTutorMode = activeTab === 'tutor' || activeTab === 'tutor_portal';

  const triggerSelectionHaptic = () => {
    try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged?.(); } catch (_) {}
  };

  const tabs = isTutorMode
    ? [
        { id: 'tutor', label: t.tabs?.becomeTutor || 'Tutor Registration', icon: GraduationCap },
        { id: 'tutor_portal', label: t.tabs?.myAssignments || 'My Tutor Portal', icon: Briefcase },
      ]
    : [
        { id: 'parent', label: t.tabs?.findTutor || 'Find a Tutor', icon: Search },
        { id: 'parent_portal', label: t.tabs?.myRequests || 'My Parent Portal', icon: ClipboardList },
      ];

  return (
    <div className="mb-4 px-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="h-px flex-1 bg-line" />
        <span className="text-[9px] font-black uppercase tracking-[0.18em] text-citrus">
          {isTutorMode ? (lang === 'am' ? 'የአስጠኚ ፖርታል' : 'Tutor space') : (lang === 'am' ? 'የወላጅ ፖርታል' : 'Parent space')}
        </span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <div className="grid grid-cols-2 gap-1.5 rounded-2xl border border-line bg-white/70 p-1 shadow-sm">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => { triggerSelectionHaptic(); onSelectTab(tab.id); }}
              className={`flex items-center justify-center gap-1.5 rounded-xl px-2.5 py-2.5 text-[10px] font-black transition-all ${
                isActive
                  ? 'border border-citrus/50 bg-citrus/20 text-ink shadow-sm'
                  : 'text-muted hover:bg-white hover:text-ink'
              }`}
            >
              <Icon className={`h-3.5 w-3.5 shrink-0 ${isActive ? 'text-pine' : 'text-muted'}`} />
              <span className="truncate">{tab.label}</span>
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={() => { triggerSelectionHaptic(); onSelectTab('home'); }}
        className="mx-auto mt-2 flex items-center gap-1 rounded-full px-3 py-1.5 text-[9px] font-bold text-muted transition hover:bg-white hover:text-pine"
      >
        <ArrowLeft className="h-3 w-3" />
        <span>{lang === 'am' ? 'ወደ ዋና ገጽ' : 'Back to main home'}</span>
      </button>
    </div>
  );
}
