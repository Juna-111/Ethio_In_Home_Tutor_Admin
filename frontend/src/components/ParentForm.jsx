import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, Check, Calculator } from 'lucide-react';
import {
  SUBCITIES,
  STUDENT_LEVELS,
  SUBJECTS_LIST,
  DAYS_OF_WEEK,
  SESSION_DURATIONS,
  PREFERRED_EXPERIENCES
} from '../constants/options';
import { TRANSLATIONS } from '../constants/translations';
import { getParentChildren, submitParentRequest } from '../services/api';
import { normalizeEthiopianPhone } from '../utils/phone';

export default function ParentForm({ user, lang, onSuccess }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;
  const choices = t.choices || {};

  const [children, setChildren] = useState([]);
  const [targetTutor, setTargetTutor] = useState(null);
  const [formData, setFormData] = useState({
    parent_name: user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : '',
    child_id: '',
    child_name: '',
    phone_number: '',
    student_level: '',
    subjects: [],
    preferred_gender: 'No preference',
    preferred_experience: '',
    location_subcity: '',
    location_landmark: '',
    schedule_days: [],
    time_slot: '',
    session_duration: '',
    budget_etb: ''
  });

  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [globalError, setGlobalError] = useState(null);

  useEffect(() => {
    getParentChildren().then((result) => setChildren(result.children || [])).catch(() => {});
    try {
      const raw = sessionStorage.getItem('marketplace_target_tutor');
      if (raw) setTargetTutor(JSON.parse(raw));
    } catch (_) {}
  }, []);

  useEffect(() => {
    if (user && !formData.parent_name) {
      const name = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || '';
      if (name) {
        setFormData((prev) => ({ ...prev, parent_name: name }));
      }
    }
  }, [user]);

  // Parse numeric duration hours
  const getDurationHours = (durStr) => {
    if (!durStr) return 0;
    const match = durStr.match(/([\d.]+)/);
    return match ? parseFloat(match[1]) : 1;
  };

  // Dynamic monthly calculation: Rate * Duration * Sessions/Week * 4
  const hourlyRate = parseFloat(formData.budget_etb) || 0;
  const durationHours = getDurationHours(formData.session_duration);
  const sessionsPerWeek = formData.schedule_days.length;
  const estimatedMonthly = Math.round(hourlyRate * (durationHours || 1) * (sessionsPerWeek || 1) * 4);

  const toggleSubject = (subject) => {
    setFormData((prev) => {
      const exists = prev.subjects.includes(subject);
      const next = exists ? prev.subjects.filter((s) => s !== subject) : [...prev.subjects, subject];
      if (next.length > 0 && errors.subjects) {
        setErrors((errs) => ({ ...errs, subjects: null }));
      }
      return { ...prev, subjects: next };
    });
  };

  const toggleDay = (day) => {
    setFormData((prev) => {
      const exists = prev.schedule_days.includes(day);
      const next = exists ? prev.schedule_days.filter((d) => d !== day) : [...prev.schedule_days, day];
      if (next.length > 0 && errors.schedule_days) {
        setErrors((errs) => ({ ...errs, schedule_days: null }));
      }
      return { ...prev, schedule_days: next };
    });
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.parent_name.trim()) {
      newErrors.parent_name = t.validation.required;
    }
    const normalizedPhone = normalizeEthiopianPhone(formData.phone_number);
    if (!formData.phone_number.trim()) {
      newErrors.phone_number = t.validation.required;
    } else if (!normalizedPhone) {
      newErrors.phone_number = t.validation.phoneInvalid;
    }
    if (!formData.child_id && !formData.child_name.trim()) {
      newErrors.child_name = t.validation.required;
    }
    if (!formData.student_level) {
      newErrors.student_level = t.validation.required;
    }
    if (formData.subjects.length === 0) {
      newErrors.subjects = t.validation.atLeastOneSubject;
    }
    if (!formData.location_subcity) {
      newErrors.location_subcity = t.validation.required;
    }
    if (formData.schedule_days.length === 0) {
      newErrors.schedule_days = t.validation.atLeastOneDay;
    }
    if (!formData.time_slot.trim()) {
      newErrors.time_slot = t.validation.required;
    }
    if (!formData.session_duration) {
      newErrors.session_duration = t.validation.required;
    }
    if (!formData.budget_etb) {
      newErrors.budget_etb = t.validation.required;
    } else if (parseFloat(formData.budget_etb) <= 0) {
      newErrors.budget_etb = t.validation.budgetMin;
    }
    if (!formData.preferred_experience) {
      newErrors.preferred_experience = t.validation.required;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGlobalError(null);

    if (!validate()) {
      setGlobalError(t.validation.required);
      return;
    }

    setLoading(true);

    try {
      const payload = {
        telegram_user_id: user?.id || null,
        child_id: formData.child_id ? parseInt(formData.child_id, 10) : null,
        child_name: formData.child_id ? null : formData.child_name.trim(),
        preferred_tutor_id: targetTutor?.id || null,
        parent_name: formData.parent_name.trim(),
        phone_number: normalizeEthiopianPhone(formData.phone_number) || formData.phone_number.trim(),
        student_level: formData.student_level,
        subjects: formData.subjects,
        preferred_gender: formData.preferred_gender,
        preferred_experience: formData.preferred_experience,
        location_subcity: formData.location_subcity,
        location_landmark: formData.location_landmark.trim() || null,
        schedule_days: formData.schedule_days,
        time_slot: formData.time_slot.trim(),
        session_duration: formData.session_duration,
        budget_etb: parseFloat(formData.budget_etb)
      };

      const result = await submitParentRequest(payload);
      try { sessionStorage.removeItem('marketplace_target_tutor'); } catch (_) {}
      onSuccess(result, 'parent');
    } catch (err) {
      setGlobalError(err.message || t.messages.requestFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="px-4 pb-12 space-y-5">
      {globalError && (
        <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-2xl flex items-start space-x-2.5 transition-all duration-200">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <span className="leading-relaxed whitespace-pre-line font-medium">{globalError}</span>
        </div>
      )}

      {/* Parent Contact Details */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{t.parentForm.sectionContact}</h2>
        
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {t.parentForm.parentName} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder={t.parentForm.parentNamePlaceholder}
            value={formData.parent_name}
            onChange={(e) => {
              setFormData({ ...formData, parent_name: e.target.value });
              if (errors.parent_name) setErrors({ ...errors, parent_name: null });
            }}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none ${
              errors.parent_name
                ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100'
                : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10'
            }`}
          />
          {errors.parent_name && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.parent_name}</p>}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-xs font-semibold text-gray-700">
              {t.parentForm.phone} <span className="text-red-500">*</span>
            </label>
            <span className="text-[10px] text-muted font-medium">09... / 07...</span>
          </div>
          <div className="relative flex items-center">
            <div className="absolute left-3 flex items-center space-x-1 text-xs font-bold text-muted pointer-events-none select-none border-r border-line pr-2">
              <span className="text-sm">🇪🇹</span>
              <span>+251</span>
            </div>
            <input
              type="tel"
              placeholder="0911 223 344"
              value={formData.phone_number}
              onChange={(e) => {
                setFormData({ ...formData, phone_number: e.target.value });
                if (errors.phone_number) setErrors({ ...errors, phone_number: null });
              }}
              className={`w-full text-xs pl-[76px] pr-3.5 py-2.5 rounded-xl border transition focus:outline-none ${
                errors.phone_number
                  ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100'
                  : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10'
              }`}
            />
          </div>
          {errors.phone_number && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.phone_number}</p>}
        </div>
      </div>

      {/* Student Academic Details */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{t.parentForm.sectionStudent}</h2>
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Student / child <span className="text-red-500">*</span></label>
          {children.length > 0 && (
            <select value={formData.child_id} onChange={(e) => setFormData({ ...formData, child_id: e.target.value, child_name: '' })} className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-line bg-white focus:outline-none focus:border-pine">
              <option value="">New child</option>
              {children.map((child) => <option key={child.id} value={child.id}>{child.name}</option>)}
            </select>
          )}
          {!formData.child_id && (
            <input value={formData.child_name} onChange={(e) => setFormData({ ...formData, child_name: e.target.value })} placeholder="Child's name" className="mt-2 w-full text-xs px-3.5 py-2.5 rounded-xl border border-line focus:outline-none focus:border-pine" />
          )}
          {targetTutor && <p className="mt-2 rounded-xl bg-citrus/10 border border-citrus/30 p-2 text-[10px] font-bold text-ink">Direct request for {targetTutor.full_name}. The tutor must still accept before assignment.</p>}
          {errors.child_name && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.child_name}</p>}
        </div>
        
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">
            {t.parentForm.studentLevel} <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.student_level}
            onChange={(e) => {
              setFormData({ ...formData, student_level: e.target.value });
              if (errors.student_level) setErrors({ ...errors, student_level: null });
            }}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none bg-white font-medium ${
              errors.student_level
                ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100 text-red-900'
                : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10 text-ink'
            }`}
          >
            <option value="">{t.parentForm.selectGradePlaceholder}</option>
            {STUDENT_LEVELS.map((level) => (
              <option key={level} value={level}>{choices.studentLevels?.[level] || level}</option>
            ))}
          </select>
          {errors.student_level && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.student_level}</p>}
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">
              {t.parentForm.subjectsNeeded} <span className="text-red-500">*</span>
            </label>
            <span className="text-[11px] text-pine font-semibold">{formData.subjects.length} {t.parentForm.subjectsSelected}</span>
          </div>
          <div className={`flex flex-wrap gap-1.5 p-2 rounded-xl border transition ${
            errors.subjects ? 'border-red-300 bg-red-50/10' : 'border-transparent'
          }`}>
            {SUBJECTS_LIST.map((subject) => {
              const selected = formData.subjects.includes(subject);
              return (
                <button
                  key={subject}
                  type="button"
                  onClick={() => toggleSubject(subject)}
                  className={`py-1.5 px-3 rounded-full text-xs font-medium transition flex items-center space-x-1 ${
                    selected
                      ? 'bg-pine text-paper shadow-sm font-semibold'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {selected && <Check className="w-3 h-3 mr-0.5" />}
                  <span>{choices.subjects?.[subject] || subject}</span>
                </button>
              );
            })}
          </div>
          {errors.subjects && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.subjects}</p>}
        </div>
      </div>

      {/* Location */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{t.parentForm.sectionLocation}</h2>
        
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {t.parentForm.subcity} <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.location_subcity}
            onChange={(e) => {
              setFormData({ ...formData, location_subcity: e.target.value });
              if (errors.location_subcity) setErrors({ ...errors, location_subcity: null });
            }}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none bg-white font-medium ${
              errors.location_subcity
                ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100 text-red-900'
                : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10 text-ink'
            }`}
          >
            <option value="">{t.parentForm.selectSubcityPlaceholder}</option>
            {SUBCITIES.map((subcity) => (
              <option key={subcity} value={subcity}>{choices.subcities?.[subcity] || subcity}</option>
            ))}
          </select>
          {errors.location_subcity && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.location_subcity}</p>}
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">{t.parentForm.landmark}</label>
          <input
            type="text"
            placeholder={t.parentForm.landmarkPlaceholder}
            value={formData.location_landmark}
            onChange={(e) => setFormData({ ...formData, location_landmark: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-line focus:outline-none focus:border-pine transition"
          />
        </div>
      </div>

      {/* Schedule & Budget Calculation */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{t.parentForm.sectionSchedule}</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-2">
            {t.parentForm.preferredDays} <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-4 gap-1.5">
            {DAYS_OF_WEEK.map((day) => {
              const selected = formData.schedule_days.includes(day);
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => toggleDay(day)}
                  className={`py-2 rounded-xl text-xs font-semibold transition ${
                    selected
                      ? 'bg-pine text-paper shadow-sm'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {choices.days?.[day] || day}
                </button>
              );
            })}
          </div>
          {errors.schedule_days && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.schedule_days}</p>}
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">
            {t.parentForm.timeSlot} <span className="text-red-500">*</span>
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {[
              { label: lang === 'am' ? 'ከቀኑ 10:30 - 12:30' : '4:30 PM - 6:30 PM', val: '4:30 PM - 6:30 PM' },
              { label: lang === 'am' ? 'ከጠዋቱ 3:00 - 5:00' : '9:00 AM - 11:00 AM', val: '9:00 AM - 11:00 AM' },
              { label: lang === 'am' ? 'ቅዳሜ/እሑድ 4:00 - 6:00' : 'Weekend 10 AM - 12 PM', val: 'Weekend 10:00 AM - 12:00 PM' },
              { label: lang === 'am' ? 'ማታ 12:00 - 2:00' : '6:00 PM - 8:00 PM', val: '6:00 PM - 8:00 PM' }
            ].map((preset) => (
              <button
                key={preset.val}
                type="button"
                onClick={() => {
                  setFormData((prev) => ({ ...prev, time_slot: preset.val }));
                  if (errors.time_slot) setErrors((errs) => ({ ...errs, time_slot: null }));
                }}
                className={`py-1 px-2.5 rounded-lg text-[11px] font-medium border transition cursor-pointer ${
                  formData.time_slot === preset.val
                    ? 'border-pine bg-pine/10 text-pine font-bold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            placeholder={t.parentForm.timeSlotPlaceholder}
            value={formData.time_slot}
            onChange={(e) => {
              setFormData({ ...formData, time_slot: e.target.value });
              if (errors.time_slot) setErrors({ ...errors, time_slot: null });
            }}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none ${
              errors.time_slot
                ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100'
                : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10'
            }`}
          />
          {errors.time_slot && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.time_slot}</p>}
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {t.parentForm.duration} <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.session_duration}
            onChange={(e) => {
              setFormData({ ...formData, session_duration: e.target.value });
              if (errors.session_duration) setErrors({ ...errors, session_duration: null });
            }}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none bg-white font-medium ${
              errors.session_duration
                ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100 text-red-900'
                : 'border-line focus:border-pine focus:ring-2 focus:ring-pine/10 text-ink'
            }`}
          >
            <option value="">{t.parentForm.selectDurationPlaceholder}</option>
            {SESSION_DURATIONS.map((dur) => (
              <option key={dur} value={dur}>{choices.durations?.[dur] || dur}</option>
            ))}
          </select>
          {errors.session_duration && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.session_duration}</p>}
        </div>

        {/* Budget per Hour with Dynamic Monthly Estimation */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {t.parentForm.budgetPerHour} <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              type="number"
              min="50"
              step="25"
              placeholder={t.parentForm.budgetPlaceholder}
              value={formData.budget_etb}
              onChange={(e) => {
                setFormData({ ...formData, budget_etb: e.target.value });
                if (errors.budget_etb) setErrors({ ...errors, budget_etb: null });
              }}
              className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition focus:outline-none font-semibold ${
                errors.budget_etb
                  ? 'border-red-500 bg-red-50/20 ring-2 ring-red-100'
                  : 'border-line focus:border-pine'
              }`}
            />
            <span className="absolute right-3.5 top-2.5 text-xs text-gray-400 font-medium">{t.parentForm.perHour}</span>
          </div>
          {errors.budget_etb && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.budget_etb}</p>}

          {/* Dynamic Monthly Cost Card */}
          <div className="mt-2.5 p-3 rounded-xl bg-pine/5 border border-pine/15 flex items-start space-x-2.5">
            <Calculator className="w-4 h-4 text-pine shrink-0 mt-0.5" />
            <div className="text-xs">
              <span className="text-gray-600">{t.parentForm.estimatedMonthly}: </span>
              <span className="font-bold text-pine">
                {hourlyRate > 0 ? `≈ ${estimatedMonthly.toLocaleString()} ${t.parentForm.perMonth}` : `— ${t.parentForm.perMonth}`}
              </span>
              <p className="text-[10px] text-gray-400 mt-0.5">{t.parentForm.formulaNote}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tutor Preferences */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{t.parentForm.sectionPreferences}</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">{t.parentForm.genderPref}</label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { val: "No preference", label: t.options.noPreference },
              { val: "Male", label: t.options.male },
              { val: "Female", label: t.options.female }
            ].map(({ val, label }) => (
              <button
                key={val}
                type="button"
                onClick={() => setFormData({ ...formData, preferred_gender: val })}
                className={`py-2 px-1 text-[11px] rounded-xl font-medium border transition text-center ${
                  formData.preferred_gender === val
                    ? 'border-pine bg-pine/10 text-pine font-semibold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">
            {t.parentForm.expPref} <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-3 gap-2">
            {PREFERRED_EXPERIENCES.map((exp) => (
              <button
                key={exp}
                type="button"
                onClick={() => {
                  setFormData({ ...formData, preferred_experience: exp });
                  if (errors.preferred_experience) setErrors({ ...errors, preferred_experience: null });
                }}
                className={`py-2 px-1 text-[10px] sm:text-[11px] rounded-xl font-medium border transition text-center leading-tight ${
                  formData.preferred_experience === exp
                    ? 'border-pine bg-pine/10 text-pine font-semibold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {choices.experiences?.[exp] || exp}
              </button>
            ))}
          </div>
          {errors.preferred_experience && <p className="text-[11px] text-red-500 mt-1 font-medium">{errors.preferred_experience}</p>}
        </div>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3.5 px-4 rounded-2xl font-bold text-sm bg-pine hover:bg-ink active:scale-[0.99] text-paper shadow-lg shadow-pine/20 transition disabled:opacity-60 flex items-center justify-center space-x-2 cursor-pointer"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>{t.parentForm.submittingBtn}</span>
          </>
        ) : (
          <span>{t.parentForm.submitBtn}</span>
        )}
      </button>
    </form>
  );
}
