import React from 'react';
import { Search, GraduationCap } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function TabNavigation({ activeTab, onSelectTab, lang }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  return (
    <div className="px-4 mb-4">
      <div className="bg-gray-200/80 p-1 rounded-2xl flex space-x-1 shadow-inner">
        <button
          type="button"
          onClick={() => onSelectTab('parent')}
          className={`flex-1 py-2.5 px-3 rounded-xl font-semibold text-xs transition-all flex items-center justify-center space-x-2 ${
            activeTab === 'parent'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Search className="w-4 h-4" />
          <span>{t.tabs.findTutor}</span>
        </button>

        <button
          type="button"
          onClick={() => onSelectTab('tutor')}
          className={`flex-1 py-2.5 px-3 rounded-xl font-semibold text-xs transition-all flex items-center justify-center space-x-2 ${
            activeTab === 'tutor'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <GraduationCap className="w-4 h-4" />
          <span>{t.tabs.becomeTutor}</span>
        </button>
      </div>
    </div>
  );
}
