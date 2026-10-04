import React from 'react';
import { Search, GraduationCap, ClipboardList, Briefcase, Users } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function TabNavigation({ activeTab, onSelectTab, lang }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  // Determine current active role from activeTab
  const isTutorMode = activeTab === 'tutor' || activeTab === 'tutor_portal';

  const triggerSelectionHaptic = () => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.selectionChanged?.();
    } catch (_) {}
  };

  const handleRoleChange = (role) => {
    triggerSelectionHaptic();
    if (role === 'parent') {
      onSelectTab('parent');
    } else {
      onSelectTab('tutor');
    }
  };

  const parentSubTabs = [
    { id: 'parent', label: t.tabs?.findTutor || 'Find Tutor', icon: Search },
    { id: 'parent_portal', label: t.tabs?.myRequests || 'My Requests', icon: ClipboardList },
  ];

  const tutorSubTabs = [
    { id: 'tutor', label: t.tabs?.becomeTutor || 'Become Tutor', icon: GraduationCap },
    { id: 'tutor_portal', label: t.tabs?.myAssignments || 'My Teaching', icon: Briefcase },
  ];

  const subTabs = isTutorMode ? tutorSubTabs : parentSubTabs;

  return (
    <div className="px-4 mb-3 space-y-2">
      {/* 1. Main Role Selector (Parent vs Tutor) */}
      <div className="grid grid-cols-2 gap-1.5 p-1 bg-line/80 rounded-2xl border border-line shadow-inner">
        <button
          type="button"
          onClick={() => handleRoleChange('parent')}
          className={`py-2 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center space-x-1.5 cursor-pointer ${
            !isTutorMode
              ? 'bg-pine text-paper shadow-sm'
              : 'text-muted hover:text-ink hover:bg-white/40'
          }`}
        >
          <Users className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{lang === 'am' ? 'የወላጅ ክፍል (Parent)' : 'Parent / Student'}</span>
        </button>

        <button
          type="button"
          onClick={() => handleRoleChange('tutor')}
          className={`py-2 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center space-x-1.5 cursor-pointer ${
            isTutorMode
              ? 'bg-pine text-paper shadow-sm'
              : 'text-muted hover:text-ink hover:bg-white/40'
          }`}
        >
          <GraduationCap className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{lang === 'am' ? 'የመምህር ክፍል (Tutor)' : 'Tutor / Educator'}</span>
        </button>
      </div>

      {/* 2. Sub-tabs strictly scoped to the active role */}
      <div className="grid grid-cols-2 gap-1.5 p-1 bg-white/70 rounded-xl border border-line shadow-xs">
        {subTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => { triggerSelectionHaptic(); onSelectTab(tab.id); }}
              className={`py-2 px-2.5 rounded-lg font-bold text-xs transition-all flex items-center justify-center space-x-1.5 cursor-pointer ${
                isActive
                  ? 'bg-citrus/25 text-ink border border-citrus/50 shadow-xs'
                  : 'text-muted hover:text-ink hover:bg-white/50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-pine' : 'text-muted'}`} />
              <span className="truncate">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
