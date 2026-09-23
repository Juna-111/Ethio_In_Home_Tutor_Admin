import React, { useEffect } from 'react';
import { CheckCircle2, X, ArrowRight } from 'lucide-react';

export default function SuccessModal({ data, type, onClose }) {
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
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-sm rounded-3xl p-6 shadow-2xl text-center relative border border-gray-100">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-1.5 rounded-full text-gray-400 hover:text-gray-600 bg-gray-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-inner">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <h3 className="text-xl font-bold text-gray-900 mb-1">
          {type === 'parent' ? 'Request Submitted!' : 'Registration Submitted!'}
        </h3>
        
        <p className="text-xs text-gray-500 mb-5 leading-relaxed">
          {type === 'parent'
            ? 'Your tutoring request has been forwarded to our coordinators. We are currently matching verified tutors.'
            : 'Your profile has been forwarded for admin verification. You will receive a Telegram alert once verified.'}
        </p>

        <div className="bg-gray-50 rounded-2xl p-4 mb-6 text-left border border-gray-100 space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 font-medium">Record ID:</span>
            <span className="font-bold text-gray-900">#{data?.id || '—'}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 font-medium">Initial Status:</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">
              ⏳ Pending
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 font-medium">Contact:</span>
            <span className="font-semibold text-gray-900">{data?.phone_number || '—'}</span>
          </div>
        </div>

        <div className="space-y-2.5">
          <button
            type="button"
            onClick={onClose}
            className="w-full py-3 px-4 rounded-xl font-semibold text-xs bg-blue-600 hover:bg-blue-700 text-white transition shadow-sm shadow-blue-500/20"
          >
            Submit Another Request
          </button>
          <button
            type="button"
            onClick={handleTelegramClose}
            className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-gray-500 hover:text-gray-800 bg-gray-100 transition"
          >
            Done & Close App
          </button>
        </div>
      </div>
    </div>
  );
}
