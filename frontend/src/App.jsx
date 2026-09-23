import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import TabNavigation from './components/TabNavigation';
import ParentForm from './components/ParentForm';
import TutorForm from './components/TutorForm';
import SuccessModal from './components/SuccessModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('parent');
  const [user, setUser] = useState(null);
  const [submissionSuccess, setSubmissionSuccess] = useState(null);
  const [lang, setLang] = useState('en');

  const toggleLanguage = () => {
    setLang((prev) => (prev === 'en' ? 'am' : 'en'));
  };

  useEffect(() => {
    try {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        tg.ready();
        tg.expand();
        if (tg.initDataUnsafe?.user) {
          setUser(tg.initDataUnsafe.user);
        }
      }
    } catch (e) {
      console.info("Telegram WebApp initialization skipped (running in standard browser mode).");
    }
  }, []);

  const handleSuccess = (result, type) => {
    setSubmissionSuccess({ data: result, type });
  };

  const handleCloseModal = () => {
    setSubmissionSuccess(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col max-w-md mx-auto relative shadow-2xl overflow-x-hidden">
      {/* Brand Header */}
      <Header user={user} lang={lang} onToggleLang={toggleLanguage} />

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onSelectTab={setActiveTab} lang={lang} />

      {/* Main Content Area */}
      <main className="flex-1">
        {activeTab === 'parent' ? (
          <ParentForm user={user} lang={lang} onSuccess={handleSuccess} />
        ) : (
          <TutorForm user={user} lang={lang} onSuccess={handleSuccess} />
        )}
      </main>

      {/* Confirmation Modal */}
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
