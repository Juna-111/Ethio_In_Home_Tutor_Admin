import React, { useEffect } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { TRANSLATIONS } from '../constants/translations';

export default function SuccessModal({ data, type, lang, onClose }) {
  const t = (TRANSLATIONS[lang] || TRANSLATIONS.en).modal;

  useEffect(() => {
    // Trigger Telegram Haptic Feedback on successful modal display
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      }
    } catch (e) {
      // Ignore in non-TMA browser mode
    }
  }, []);

  const handleTelegramClose = () => {
    try {
      if (window.Telegram?.WebApp?.close) {
        window.Telegram.WebApp.close();
      } else {
        onClose();
      }
    } catch {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-200">
      <div className="bg-paper w-full max-w-sm rounded-3xl p-6 shadow-2xl text-center relative border border-line">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-1.5 rounded-full text-muted hover:text-ink bg-line/60 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="w-16 h-16 bg-green-100 text-green rounded-full flex items-center justify-center mx-auto mb-4 shadow-inner">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <h3 className="text-xl font-bold text-ink mb-1">
          {type === 'parent' ? t.parentTitle : t.tutorTitle}
        </h3>
        
        <p className="text-xs text-muted mb-5 leading-relaxed bg-white/70 p-3 rounded-xl border border-line">
          {type === 'parent' ? t.parentTrustMsg : t.tutorTrustMsg}
        </p>

        <div className="bg-white/80 rounded-2xl p-4 mb-6 text-left border border-line space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-muted font-medium">{t.recordId}:</span>
            <span className="font-bold text-ink">#{data?.id || '—'}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted font-medium">{t.initialStatus}:</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-citrus/15 text-citrus">
              {t.statusPending}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted font-medium">{t.contact}:</span>
            <span className="font-semibold text-ink">{data?.phone_number || '—'}</span>
          </div>
        </div>

        <div className="space-y-2.5">
          <button
            type="button"
            onClick={onClose}
            className="w-full py-3 px-4 rounded-xl font-semibold text-xs bg-pine hover:bg-ink text-paper transition shadow-sm"
          >
            {t.submitAnother}
          </button>
          <button
            type="button"
            onClick={handleTelegramClose}
            className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-muted hover:text-ink bg-line/60 transition"
          >
            {t.closeApp}
          </button>
        </div>
      </div>
    </div>
  );
}
