import React, { useState, useEffect } from 'react';
import { 
  Briefcase, 
  Users, 
  DollarSign, 
  BookOpen, 
  MapPin, 
  Calendar, 
  Phone, 
  AlertCircle, 
  Loader2,
  CheckCircle2,
  MessageSquare,
  RotateCw,
  GraduationCap
} from 'lucide-react';
import { getTutorMyAssignments } from '../services/api';

export default function TutorPortal({ user, lang, onSelectTab }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAssignments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTutorMyAssignments();
      setData(res);
    } catch (err) {
      setError(err.message || 'Could not load your tutor assignments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
  }, []);

  const assignments = data?.assignments || data?.items || [];

  const summary = {
    total_assignments: assignments.length,
    active_assignments: data?.active_count ?? (data?.summary?.active_assignments || assignments.filter((a) => a.status === 'active').length),
    completed_assignments: assignments.filter((a) => a.status === 'completed').length,
    estimated_monthly_earnings: data?.total_earnings_estimate ?? (data?.summary?.estimated_monthly_earnings || 0)
  };

  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'active') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green/15 text-green">Active</span>;
    }
    if (s === 'completed') {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-muted/20 text-muted">Completed</span>;
    }
    return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-pine/10 text-pine">{status}</span>;
  };

  return (
    <div className="px-4 pb-12 space-y-4">
      <div className="bg-paper p-4 rounded-2xl border border-line shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-ink flex items-center space-x-2">
            <Briefcase className="w-4 h-4 text-pine" />
            <span>{lang === 'am' ? 'የማስተምራቸው ተማሪዎች' : 'My Tutoring Assignments'}</span>
          </h2>
          <p className="text-xs text-muted mt-1">
            {lang === 'am'
              ? 'ንቁ ተማሪዎችዎን፣ የትምህርት መርሃ-ግብርዎን እና ወርሃዊ ገቢዎን ይቆጣጠሩ።'
              : 'Track your assigned students, weekly tutoring schedules, and earnings.'}
          </p>
        </div>
        <button
          type="button"
          onClick={loadAssignments}
          disabled={loading}
          className="p-2 rounded-xl border border-line hover:bg-line/40 text-muted hover:text-ink transition cursor-pointer shrink-0 ml-2"
          title={lang === 'am' ? 'አድስ' : 'Refresh'}
        >
          <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin text-pine' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-8 bg-paper rounded-2xl border border-line text-muted">
          <Loader2 className="w-6 h-6 animate-spin text-pine mb-2" />
          <span className="text-xs">{lang === 'am' ? 'በመጫን ላይ...' : 'Loading your assignments...'}</span>
        </div>
      ) : error ? (
        <div className="p-5 bg-paper rounded-2xl border border-line text-center space-y-3 shadow-sm">
          <div className="w-12 h-12 rounded-full bg-pine/10 text-pine mx-auto flex items-center justify-center">
            {error.includes('not found') || error.includes('404') ? (
              <GraduationCap className="w-6 h-6 text-pine" />
            ) : (
              <AlertCircle className="w-6 h-6 text-coral" />
            )}
          </div>
          <p className="text-xs font-bold text-ink">
            {error.includes('not found') || error.includes('404')
              ? (lang === 'am' ? 'የመምህር ፕሮፋይል አልተገኘም' : 'No Tutor Profile Found')
              : error.includes('authentication') || error.includes('401')
              ? (lang === 'am' ? 'የቴሌግራም ማረጋገጫ ያስፈልጋል' : 'Telegram Mini App Account Needed')
              : (lang === 'am' ? 'ማስተማሪያዎችን ማምጣት አልተቻለም' : 'Could Not Load Assignments')}
          </p>
          <p className="text-xs text-muted leading-relaxed">
            {error.includes('not found') || error.includes('404')
              ? (lang === 'am'
                  ? 'የማስተማር እድሎችን ለማግኘት እባክዎን መጀመሪያ እንደ አስጠኚ ይመዝገቡ።'
                  : 'You have not registered as a tutor yet. Complete tutor registration to receive student assignments.')
              : error.includes('authentication') || error.includes('401')
              ? (lang === 'am'
                  ? 'የእርስዎን ማስተማሪያዎች ለማየት እባክዎ ይህን መተግበሪያ በቴሌግራም ውስጥ ይክፈቱት።'
                  : 'Open MentorLink directly inside Telegram to view your tutoring assignments.')
              : error}
          </p>
          <div className="flex items-center justify-center space-x-2 pt-1">
            {onSelectTab && (error.includes('not found') || error.includes('404')) ? (
              <button
                type="button"
                onClick={() => onSelectTab('tutor')}
                className="py-2.5 px-4 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm cursor-pointer"
              >
                {lang === 'am' ? 'እንደ መምህር ይመዝገቡ' : 'Register as a Tutor'}
              </button>
            ) : (
              <button
                type="button"
                onClick={loadAssignments}
                className="py-2 px-4 rounded-xl font-bold text-xs bg-pine text-paper hover:bg-ink transition shadow-sm cursor-pointer"
              >
                {lang === 'am' ? 'እንደገና ይሞክሩ' : 'Retry'}
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-paper p-3 rounded-2xl border border-line shadow-sm text-center">
              <span className="text-[10px] font-bold text-muted uppercase tracking-wider block">Active</span>
              <span className="text-lg font-black text-pine">{summary.active_assignments}</span>
            </div>
            <div className="bg-paper p-3 rounded-2xl border border-line shadow-sm text-center">
              <span className="text-[10px] font-bold text-muted uppercase tracking-wider block">Total</span>
              <span className="text-lg font-black text-ink">{summary.total_assignments}</span>
            </div>
            <div className="bg-paper p-3 rounded-2xl border border-line shadow-sm text-center">
              <span className="text-[10px] font-bold text-muted uppercase tracking-wider block">Est. Monthly</span>
              <span className="text-xs font-black text-green mt-1 block">
                {Math.round(summary.estimated_monthly_earnings || 0).toLocaleString()} ETB
              </span>
            </div>
          </div>

          {/* Assignments List */}
          {assignments.length === 0 ? (
            <div className="p-8 bg-paper rounded-2xl border border-line text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-line/60 text-muted mx-auto flex items-center justify-center">
                <Users className="w-6 h-6" />
              </div>
              <p className="text-xs text-muted font-medium">
                {lang === 'am' ? 'እስካሁን የተመደበልዎት ተማሪ የለም።' : 'You do not have any student assignments yet.'}
              </p>
              <p className="text-[11px] text-muted">
                {lang === 'am' 
                  ? 'አዲስ የማስተማር እድሎች ሲኖሩ በቴሌግራም መልእክት ይደርስዎታል።'
                  : 'You will receive a notification in Telegram when a matching parent request is confirmed.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {assignments.map((item) => (
                <div key={item.assignment_id || item.id} className="bg-paper p-4 rounded-2xl border border-line shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-ink">Assignment #{item.assignment_id || item.id}</span>
                      <p className="text-xs font-bold text-pine">{item.student_name_context || item.parent_name}</p>
                    </div>
                    {getStatusBadge(item.status)}
                  </div>

                  <div className="text-xs text-muted space-y-1.5 bg-white/60 p-3 rounded-xl border border-line">
                    <div className="flex items-center space-x-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-pine shrink-0" />
                      <span className="text-ink font-semibold">{item.student_level || 'Grade Context'}</span>
                      <span>•</span>
                      <span>{(item.subjects || []).join(', ')}</span>
                    </div>

                    <div className="flex items-center space-x-1.5">
                      <MapPin className="w-3.5 h-3.5 text-muted shrink-0" />
                      <span>{item.location || item.location_subcity || 'Addis Ababa'}</span>
                    </div>

                    <div className="flex items-center space-x-1.5">
                      <Calendar className="w-3.5 h-3.5 text-muted shrink-0" />
                      <span>{item.schedule || (item.schedule_days || []).join(', ')}</span>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-line text-[11px]">
                      <span className="text-muted">Agreed Rate:</span>
                      <span className="font-bold text-ink">{item.hourly_rate_etb || item.hourly_rate} ETB / hr</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2 pt-1">
                    {item.parent_phone ? (
                      <a
                        href={`tel:${item.parent_phone}`}
                        className="flex-1 py-2 px-3 rounded-xl font-semibold text-xs bg-pine text-paper hover:bg-ink transition flex items-center justify-center space-x-1.5 shadow-sm"
                      >
                        <Phone className="w-3.5 h-3.5" />
                        <span>{lang === 'am' ? 'ወላጅን ይደውሉ' : 'Call Parent'}</span>
                      </a>
                    ) : (
                      <span className="text-xs text-muted">No phone provided</span>
                    )}

                    <a
                      href="https://t.me/MentorLinkAdmin"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="py-2 px-3 rounded-xl font-semibold text-xs border border-line text-muted hover:text-ink hover:bg-white/60 transition flex items-center justify-center space-x-1"
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      <span>{lang === 'am' ? 'ሪፖርት' : 'Report Status'}</span>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
