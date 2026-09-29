import React, { useState } from 'react';
import { CheckCircle2, Copy, Check } from 'lucide-react';

export default function UserProfile({ user, lang, role }) {
  const [copied, setCopied] = useState(false);

  const fullName = user
    ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || 'Telegram User'
    : (lang === 'am' ? 'እንግዳ ተጠቃሚ' : 'Guest Visitor');
  const username = user?.username ? `@${user.username}` : null;
  const initial = (user?.first_name || user?.username || 'U')[0].toUpperCase();

  const handleCopyId = () => {
    if (user?.id) {
      try {
        navigator.clipboard?.writeText(String(user.id));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (_) {}
    }
  };

  return (
    <div className="px-4 mb-3">
      <div className="bg-paper p-3 rounded-2xl border border-line shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pine to-citrus flex items-center justify-center text-paper font-black text-sm shadow-sm flex-shrink-0">
              {initial}
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-xs text-ink truncate max-w-[140px]">{fullName}</span>
                <span className="inline-flex items-center text-[10px] font-semibold text-green bg-green/10 px-1.5 py-0.5 rounded-full flex-shrink-0">
                  <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" />
                  {user ? (lang === 'am' ? 'የተረጋገጠ' : 'Verified') : 'Preview'}
                </span>
              </div>
              <div className="flex items-center space-x-1 text-[11px] text-muted truncate">
                {username && <span>{username}</span>}
                {user?.id && (
                  <>
                    <span>·</span>
                    <button
                      type="button"
                      onClick={handleCopyId}
                      className="hover:text-ink font-mono text-[10px] flex items-center space-x-0.5 cursor-pointer"
                      title="Copy Telegram ID"
                    >
                      <span>#{user.id}</span>
                      {copied ? <Check className="w-2.5 h-2.5 text-green" /> : <Copy className="w-2.5 h-2.5 text-muted/60" />}
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="text-right flex-shrink-0 ml-2">
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-lg bg-pine/10 text-pine border border-pine/20">
              {role === 'parent' 
                ? (lang === 'am' ? '👨‍👩‍👧 ወላጅ' : '👨‍👩‍👧 Parent') 
                : (lang === 'am' ? '🎓 መምህር' : '🎓 Tutor')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
