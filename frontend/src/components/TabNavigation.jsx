import React from 'react';
import { Search, GraduationCap, ClipboardList, Briefcase } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function TabNavigation({ activeTab, onSelectTab, lang }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  const tabs = [
    { id: 'parent', label: t.tabs.findTutor || 'Find Tutor', icon: Search },
    { id: 'parent_portal', label: t.tabs.myRequests || 'My Requests', icon: ClipboardList },
    { id: 'tutor', label: t.tabs.becomeTutor || 'Become Tutor', icon: GraduationCap },
    { id: 'tutor_portal', label: t.tabs.myAssignments || 'My Teaching', icon: Briefcase },
  ];

  return (
    <div className="px-4 mb-4">
      <div className="grid grid-cols-2 gap-1.5 p-1.5 bg-line/60 rounded-2xl border border-line shadow-inner">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onSelectTab(tab.id)}
              className={`py-2 px-2.5 rounded-xl font-semibold text-xs transition-all flex items-center justify-center space-x-1.5 cursor-pointer ${
                isActive
                  ? 'bg-pine text-paper shadow-sm'
                  : 'text-muted hover:text-ink hover:bg-white/40'
              }`}
            >
              <Icon className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="truncate">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
