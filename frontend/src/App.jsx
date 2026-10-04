import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import TabNavigation from './components/TabNavigation';
import CustomerHome from './components/CustomerHome';
import ParentForm from './components/ParentForm';
import TutorForm from './components/TutorForm';
import ParentPortal from './components/ParentPortal';
import TutorPortal from './components/TutorPortal';
import UserProfile from './components/UserProfile';
import SuccessModal from './components/SuccessModal';
import { getTelegramInitData } from './services/api';
import { TRANSLATIONS } from './constants/translations';

const LANGUAGE_STORAGE_KEY = 'mentorlink-language';

function resolveInitialTab() {
  try {
    const tg = window.Telegram?.WebApp;
    const startParam = tg?.initDataUnsafe?.start_param || '';
    const searchParams = new URLSearchParams(window.location.search);
    const queryTab = searchParams.get('tab') || searchParams.get('startapp') || searchParams.get('start_param') || '';
    const hashStr = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
    const hashParams = new URLSearchParams(hashStr);
    const hashTab = hashParams.get('tgWebAppStartParam') || '';

    const param = (startParam || queryTab || hashTab).toLowerCase();
    if (param.includes('tutor_portal') || param.includes('assignment') || param.includes('teaching')) return 'tutor_portal';
    if (param.includes('parent_portal') || param.includes('my_requests') || param.includes('requests')) return 'parent_portal';
    if (param.includes('tutor') || param.includes('become')) return 'tutor';
    if (param.includes('parent') || param.includes('find_tutor')) return 'parent';
  } catch (_) {}
  return 'home';
}

export default function App() {
  const [activeTab, setActiveTab] = useState(resolveInitialTab);
  const [user, setUser] = useState(null);
  const [submissionSuccess, setSubmissionSuccess] = useState(null);
  const [lang, setLang] = useState(() => {
    try {
      return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === 'am' ? 'am' : 'en';
    } catch {
      return 'en';
    }
  });

  const isHome = activeTab === 'home';
  const isTutor = activeTab === 'tutor' || activeTab === 'tutor_portal';
  const role = isTutor ? 'tutor' : 'parent';

  const toggleLanguage = () => setLang((prev) => (prev === 'en' ? 'am' : 'en'));

  useEffect(() => {
    try {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        tg.ready();
        tg.expand();
        if (tg.initData) {
          try { sessionStorage.setItem('tma_init_data', tg.initData); } catch (_) {}
        }
        if (tg.initDataUnsafe?.user) setUser(tg.initDataUnsafe.user);

        if (tg.initDataUnsafe?.start_param) {
          const sp = tg.initDataUnsafe.start_param.toLowerCase();
          if (sp.includes('tutor_portal') || sp.includes('assignment') || sp.includes('teaching')) setActiveTab('tutor_portal');
          else if (sp.includes('parent_portal') || sp.includes('my_requests') || sp.includes('requests')) setActiveTab('parent_portal');
          else if (sp.includes('tutor')) setActiveTab('tutor');
          else if (sp.includes('parent')) setActiveTab('parent');
        }
      }

      const rawInitData = getTelegramInitData();
      if (rawInitData) {
        try {
          const params = new URLSearchParams(rawInitData);
          const userStr = params.get('user');
          if (userStr) {
            const parsedUser = JSON.parse(userStr);
            setUser((prev) => prev || parsedUser);
          }
        } catch (_) {}
      }
    } catch (e) {
      console.info('Telegram WebApp initialization skipped (running in standard browser mode).');
    }
  }, []);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    const backButton = tg?.BackButton;
    if (!backButton) return undefined;

    if (!isHome) {
      backButton.show();
      const handleBack = () => setActiveTab('home');
      backButton.onClick(handleBack);
      return () => {
        backButton.offClick(handleBack);
        backButton.hide();
      };
    }

    backButton.hide();
    return undefined;
  }, [isHome]);

  useEffect(() => {
    const translation = TRANSLATIONS[lang] || TRANSLATIONS.en;
    document.documentElement.lang = lang;
    document.title = translation.appTitle + ' - ' + translation.appSubtitle;
    try { window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lang); } catch {}
  }, [lang]);

  const handleSuccess = (result, type) => setSubmissionSuccess({ data: result, type });
  const handleCloseModal = () => setSubmissionSuccess(null);
  const goHome = () => setActiveTab('home');

  return (
    <div className="min-h-screen bg-[#f1f3ef] flex flex-col max-w-md mx-auto relative shadow-2xl overflow-x-hidden font-sans text-ink">
      <Header
        user={user}
        lang={lang}
        onToggleLanguage={toggleLanguage}
        showHome={!isHome}
        onHome={goHome}
      />

      {!isHome && (
        <>
          <UserProfile user={user} lang={lang} role={role} />
          <TabNavigation activeTab={activeTab} onSelectTab={setActiveTab} lang={lang} />
        </>
      )}

      <main className="flex-1">
        {isHome && <CustomerHome user={user} lang={lang} onSelectTab={setActiveTab} />}
        {activeTab === 'parent' && <ParentForm user={user} lang={lang} onSuccess={handleSuccess} />}
        {activeTab === 'parent_portal' && <ParentPortal user={user} lang={lang} onSelectTab={setActiveTab} />}
        {activeTab === 'tutor' && <TutorForm user={user} lang={lang} onSuccess={handleSuccess} />}
        {activeTab === 'tutor_portal' && <TutorPortal user={user} lang={lang} onSelectTab={setActiveTab} />}
      </main>

      {submissionSuccess && (
        <SuccessModal
          data={submissionSuccess.data}
          type={submissionSuccess.type}
          lang={lang}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
}
