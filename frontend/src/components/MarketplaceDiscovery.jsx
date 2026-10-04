import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Award, Bookmark, BookmarkCheck, CheckCircle2, ChevronDown, ChevronUp, Filter, GraduationCap, Loader2, MapPin, RefreshCw, Search, ShieldCheck, Star, X } from 'lucide-react';
import {
  applyToMarketplaceTutor,
  favoriteMarketplaceTutor,
  getMarketplaceTutor,
  getMarketplaceTutors,
  unfavoriteMarketplaceTutor,
} from '../services/api';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function MarketplaceDiscovery({ lang = 'en', onSelectTab }) {
  const isAm = lang === 'am';
  const [tutors, setTutors] = useState([]);
  const [requestId, setRequestId] = useState(null);
  const [filters, setFilters] = useState({ subject: '', grade: '', subcity: '', max_fee: '', min_rating: '', available_day: '', verified_only: 'true' });
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [favoriteBusy, setFavoriteBusy] = useState(null);
  const [applyBusy, setApplyBusy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMarketplaceTutors(filters);
      setTutors(result.tutors || []);
      setRequestId(result.request_id || null);
    } catch (err) {
      setError(err.message || (isAm ? 'አስጠኚዎችን መፈለግ አልተቻለም።' : 'Could not load tutors.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filters.subject, filters.grade, filters.subcity, filters.max_fee, filters.min_rating, filters.available_day, filters.verified_only]);

  const updateFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const toggleFavorite = async (tutor) => {
    setFavoriteBusy(tutor.id);
    setError(null);
    try {
      const result = tutor.is_favorite
        ? await unfavoriteMarketplaceTutor(tutor.id)
        : await favoriteMarketplaceTutor(tutor.id);
      setTutors((prev) => prev.map((item) => item.id === tutor.id ? { ...item, is_favorite: result.is_favorite } : item));
    } catch (err) {
      setError(err.message || (isAm ? 'ተወዳጅ ዝርዝሩን ማዘመን አልተቻለም።' : 'Could not update favorites.'));
    } finally {
      setFavoriteBusy(null);
    }
  };

  const openDetail = async (tutorId) => {
    if (expandedId === tutorId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(tutorId);
    setDetail(null);
    try {
      setDetail(await getMarketplaceTutor(tutorId));
    } catch (err) {
      setError(err.message || (isAm ? 'ፕሮፋይሉን መክፈት አልተቻለም።' : 'Could not open tutor profile.'));
    }
  };

  const apply = async (tutor) => {
    if (!requestId) {
      onSelectTab?.('parent_form');
      return;
    }
    setApplyBusy(tutor.id);
    setError(null);
    setNotice(null);
    try {
      await applyToMarketplaceTutor(tutor.id, requestId);
      setNotice(isAm ? 'ማመልከቻዎ ተልኳል። አስጠኚው ሲመልስ ያያሉ።' : 'Application sent. You will see the tutor response in your request flow.');
      await load();
    } catch (err) {
      setError(err.message || (isAm ? 'ማመልከቻውን መላክ አልተቻለም።' : 'Could not send application.'));
    } finally {
      setApplyBusy(null);
    }
  };

  const subtitle = useMemo(() => {
    if (requestId) return isAm ? 'የእርስዎ ንቁ ጥያቄ ከእነዚህ አስጠኚዎች ጋር ይዛመዳል።' : 'Your active tutoring request is used to rank the strongest matches first.';
    return isAm ? 'የተረጋገጡ አስጠኚዎችን ይመልከቱ።' : 'Browse verified tutors and create a request when you are ready to apply.';
  }, [requestId, isAm]);

  return (
    <div className="space-y-4 px-4 pb-12">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-pine via-pine to-ink p-5 text-paper shadow-xl">
        <div className="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-citrus/20 blur-2xl" />
        <div className="relative">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="text-[9px] font-black uppercase tracking-[0.18em] text-paper/60">{isAm ? 'የአስጠኚ ገበያ' : 'Tutor marketplace'}</span>
              <h2 className="mt-1 text-xl font-black">{isAm ? 'ትክክለኛውን አስጠኚ ያግኙ' : 'Find the right tutor'}</h2>
            </div>
            <button type="button" onClick={load} className="rounded-xl border border-white/10 bg-white/10 p-2 text-paper/80" aria-label="Refresh">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-2 max-w-sm text-[10px] leading-relaxed text-paper/70">{subtitle}</p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-white/10 px-2.5 py-1.5 text-[9px] font-bold"><ShieldCheck className="mr-1 inline h-3 w-3 text-citrus" />{isAm ? 'የተረጋገጡ' : 'Verified tutors'}</span>
            <span className="rounded-full bg-white/10 px-2.5 py-1.5 text-[9px] font-bold"><Star className="mr-1 inline h-3 w-3 text-citrus" />{isAm ? 'ደረጃ እና ግምገማ' : 'Ratings & reviews'}</span>
          </div>
        </div>
      </section>

      {!requestId && (
        <button type="button" onClick={() => onSelectTab?.('parent_form')} className="flex w-full items-center justify-between rounded-2xl border border-citrus/40 bg-citrus/10 p-3 text-left">
          <span><strong className="block text-xs font-black text-ink">{isAm ? 'የትምህርት ጥያቄ ያስገቡ' : 'Create a tutoring request'}</strong><small className="mt-0.5 block text-[9px] text-muted">{isAm ? 'የእርስዎን መስፈርቶች ለማዛመድ ይረዳል።' : 'This unlocks personalized recommendations and applications.'}</small></span>
          <ChevronDown className="h-4 w-4 text-pine" />
        </button>
      )}

      <section className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-pine" />
          <h3 className="text-sm font-black text-ink">{isAm ? 'ፈልግ እና አጣራ' : 'Search & filter'}</h3>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <input value={filters.subject} onChange={(e) => updateFilter('subject', e.target.value)} placeholder={isAm ? 'ትምህርት' : 'Subject'} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none" />
          <input value={filters.grade} onChange={(e) => updateFilter('grade', e.target.value)} placeholder={isAm ? 'ክፍል' : 'Grade'} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none" />
          <input value={filters.subcity} onChange={(e) => updateFilter('subcity', e.target.value)} placeholder={isAm ? 'ክፍለ ከተማ' : 'Subcity'} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none" />
          <input value={filters.max_fee} onChange={(e) => updateFilter('max_fee', e.target.value)} inputMode="numeric" placeholder={isAm ? 'ከፍተኛ ETB/hr' : 'Max ETB/hr'} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none" />
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <select value={filters.min_rating} onChange={(e) => updateFilter('min_rating', e.target.value)} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none">
            <option value="">{isAm ? 'ማንኛውም ደረጃ' : 'Any rating'}</option>
            <option value="4">4.0+</option><option value="4.5">4.5+</option>
          </select>
          <select value={filters.available_day} onChange={(e) => updateFilter('available_day', e.target.value)} className="rounded-xl border border-line bg-[#f1f3ef] px-3 py-2.5 text-xs outline-none">
            <option value="">{isAm ? 'ማንኛውም ቀን' : 'Any day'}</option>
            {DAYS.map((day) => <option key={day} value={day}>{day}</option>)}
          </select>
        </div>
      </section>

      {notice && <div className="rounded-2xl border border-green/20 bg-green/10 p-3 text-[10px] font-bold text-green">{notice}</div>}
      {error && <div className="flex items-start gap-2 rounded-2xl border border-coral/20 bg-coral/10 p-3 text-xs text-coral" role="alert"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span><button onClick={() => setError(null)} className="ml-auto"><X className="h-4 w-4" /></button></div>}

      {loading ? (
        <div className="flex min-h-48 items-center justify-center rounded-3xl border border-line bg-paper text-muted"><Loader2 className="h-7 w-7 animate-spin text-pine" /></div>
      ) : !tutors.length ? (
        <div className="rounded-3xl border border-line bg-paper p-6 text-center shadow-sm">
          <Search className="mx-auto mb-3 h-9 w-9 text-muted" />
          <h3 className="text-sm font-black text-ink">{isAm ? 'ምንም ተስማሚ አስጠኚ አልተገኘም' : 'No tutors match those filters'}</h3>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">{isAm ? 'ማጣሪያዎቹን ቀንስ ወይም የአካባቢ እና የበጀት መስፈርቶችን ይፈትሹ።' : 'Try broader filters or adjust the area and budget.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tutors.map((tutor) => {
            const isOpen = expandedId === tutor.id;
            return (
              <article key={tutor.id} className="rounded-3xl border border-line bg-paper p-4 shadow-sm">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pine/10 text-pine"><GraduationCap className="h-5 w-5" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-black text-ink">{tutor.full_name}</h3>
                        <p className="mt-0.5 text-[9px] text-muted">{tutor.university} · {tutor.department}</p>
                      </div>
                      <button type="button" onClick={() => toggleFavorite(tutor)} disabled={favoriteBusy === tutor.id} className="rounded-xl border border-line p-2 text-pine" aria-label={tutor.is_favorite ? 'Remove favorite' : 'Favorite tutor'}>
                        {tutor.is_favorite ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
                      </button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="rounded-full bg-citrus/15 px-2 py-1 text-[8px] font-black text-ink">{tutor.expected_fee_etb.toLocaleString()} ETB/hr</span>
                      <span className="rounded-full bg-pine/10 px-2 py-1 text-[8px] font-black text-pine">{tutor.years_of_experience}y exp</span>
                      {tutor.avg_rating ? <span className="rounded-full bg-[#f1f3ef] px-2 py-1 text-[8px] font-black text-ink"><Star className="mr-1 inline h-3 w-3" />{tutor.avg_rating} ({tutor.review_count})</span> : <span className="rounded-full bg-[#f1f3ef] px-2 py-1 text-[8px] font-bold text-muted">New reviews</span>}
                      {tutor.verification_complete && <span className="rounded-full bg-green/10 px-2 py-1 text-[8px] font-black text-green"><ShieldCheck className="mr-1 inline h-3 w-3" />Verified</span>}
                    </div>
                  </div>
                </div>

                {tutor.match_score > 0 && (
                  <div className="mt-3 rounded-2xl border border-citrus/30 bg-citrus/10 p-3">
                    <div className="flex items-center justify-between text-[9px]"><span className="font-black text-ink">Recommended match</span><strong className="text-pine">{Math.round(tutor.match_score)}%</strong></div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-pine" style={{ width: `${Math.min(100, tutor.match_score)}%` }} /></div>
                    <p className="mt-2 text-[9px] leading-relaxed text-muted">{tutor.match_reasons.join(' · ')}</p>
                  </div>
                )}

                <div className="mt-3 grid grid-cols-2 gap-2 text-[9px]">
                  <span className="rounded-xl bg-[#f1f3ef] p-2"><MapPin className="mr-1 inline h-3 w-3 text-pine" />{tutor.base_subcity} · {(tutor.coverage_areas || []).slice(0, 2).join(', ')}</span>
                  <span className="rounded-xl bg-[#f1f3ef] p-2"><Award className="mr-1 inline h-3 w-3 text-pine" />{(tutor.subjects_qualified || []).slice(0, 3).join(', ')}</span>
                </div>

                <div className="mt-3 flex gap-2">
                  <button type="button" onClick={() => openDetail(tutor.id)} className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-line py-2.5 text-[10px] font-black text-ink">
                    {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}{isAm ? 'ፕሮፋይል' : 'Profile'}
                  </button>
                  <button type="button" onClick={() => apply(tutor)} disabled={applyBusy === tutor.id} className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-pine py-2.5 text-[10px] font-black text-paper disabled:opacity-60">
                    {applyBusy === tutor.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}{requestId ? (isAm ? 'ላመልክት' : 'Apply') : (isAm ? 'ጥያቄ ፍጠር' : 'Create request')}
                  </button>
                </div>

                {isOpen && detail && (
                  <div className="mt-3 rounded-2xl border border-line bg-[#f1f3ef] p-3 text-[9px]">
                    <div className="grid grid-cols-2 gap-2">
                      <div><span className="text-muted">Grades</span><strong className="mt-1 block text-ink">{detail.grades_qualified.join(', ')}</strong></div>
                      <div><span className="text-muted">Education</span><strong className="mt-1 block text-ink">{detail.education_year}</strong></div>
                      <div><span className="text-muted">Availability</span><strong className="mt-1 block text-ink">{typeof detail.availability_schedule === 'string' ? detail.availability_schedule : JSON.stringify(detail.availability_schedule)}</strong></div>
                      <div><span className="text-muted">Area</span><strong className="mt-1 block text-ink">{detail.base_subcity}</strong></div>
                    </div>
                    <p className="mt-2 text-muted">{detail.match_reasons?.join(' · ') || 'Profile available for review.'}</p>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
