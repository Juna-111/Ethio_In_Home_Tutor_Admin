import React, { useState } from 'react';
import { Loader2, AlertCircle, Plus, Check } from 'lucide-react';
import {
  SUBCITIES,
  STUDENT_LEVELS,
  SUBJECTS_LIST,
  DAYS_OF_WEEK,
  SESSION_DURATIONS,
  PREFERRED_EXPERIENCES
} from '../constants/options';
import { submitParentRequest } from '../services/api';

export default function ParentForm({ user, onSuccess }) {
  const [formData, setFormData] = useState({
    parent_name: user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : '',
    phone_number: '',
    student_level: 'High School 9-10',
    subjects: ['Maths', 'Physics'],
    preferred_gender: 'No preference',
    preferred_experience: 'University Student',
    location_subcity: 'Bole',
    location_landmark: '',
    schedule_days: ['Mon', 'Wed', 'Fri'],
    time_slot: '4:30 PM - 6:30 PM',
    session_duration: '2 hrs',
    budget_etb: 4000
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggleSubject = (subject) => {
    setFormData((prev) => {
      const exists = prev.subjects.includes(subject);
      if (exists) {
        if (prev.subjects.length <= 1) return prev; // Keep at least one
        return { ...prev, subjects: prev.subjects.filter((s) => s !== subject) };
      } else {
        return { ...prev, subjects: [...prev.subjects, subject] };
      }
    });
  };

  const toggleDay = (day) => {
    setFormData((prev) => {
      const exists = prev.schedule_days.includes(day);
      if (exists) {
        if (prev.schedule_days.length <= 1) return prev;
        return { ...prev, schedule_days: prev.schedule_days.filter((d) => d !== day) };
      } else {
        return { ...prev, schedule_days: [...prev.schedule_days, day] };
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.parent_name.trim()) {
      setError("Please enter your parent name.");
      return;
    }
    if (!formData.phone_number.trim() || formData.phone_number.length < 9) {
      setError("Please enter a valid phone number (e.g. 0911223344 or +251...).");
      return;
    }
    if (formData.subjects.length === 0) {
      setError("Please select at least one subject.");
      return;
    }
    if (formData.schedule_days.length === 0) {
      setError("Please select at least one tutoring day.");
      return;
    }
    if (!formData.budget_etb || Number(formData.budget_etb) <= 0) {
      setError("Please provide a valid budget in ETB.");
      return;
    }

    setLoading(true);

    try {
      const payload = {
        telegram_user_id: user?.id || null,
        parent_name: formData.parent_name.trim(),
        phone_number: formData.phone_number.trim(),
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
      onSuccess(result, 'parent');
    } catch (err) {
      setError(err.message || "Failed to submit request. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="px-4 pb-12 space-y-5">
      {error && (
        <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-2xl flex items-start space-x-2.5 animate-in fade-in">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <span className="leading-relaxed whitespace-pre-line">{error}</span>
        </div>
      )}

      {/* Parent Basic Info */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Contact Details</h2>
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Parent Full Name *</label>
          <input
            type="text"
            required
            placeholder="e.g. Abebe Kebede"
            value={formData.parent_name}
            onChange={(e) => setFormData({ ...formData, parent_name: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Phone Number *</label>
          <input
            type="tel"
            required
            placeholder="e.g. +251 911 223344"
            value={formData.phone_number}
            onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition"
          />
        </div>
      </div>

      {/* Student Academic Details */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Student & Subjects</h2>
        
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-2">Student Educational Level *</label>
          <div className="grid grid-cols-2 gap-2">
            {STUDENT_LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => setFormData({ ...formData, student_level: level })}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-left transition ${
                  formData.student_level === level
                    ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">Subjects Needed (Multi-select) *</label>
            <span className="text-[11px] text-blue-600 font-medium">{formData.subjects.length} selected</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SUBJECTS_LIST.map((subject) => {
              const selected = formData.subjects.includes(subject);
              return (
                <button
                  key={subject}
                  type="button"
                  onClick={() => toggleSubject(subject)}
                  className={`py-1.5 px-3 rounded-full text-xs font-medium transition flex items-center space-x-1 ${
                    selected
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {selected && <Check className="w-3 h-3 mr-0.5" />}
                  <span>{subject}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Location */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Home Location</h2>
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Sub-City *</label>
          <select
            value={formData.location_subcity}
            onChange={(e) => setFormData({ ...formData, location_subcity: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition bg-white"
          >
            {SUBCITIES.map((subcity) => (
              <option key={subcity} value={subcity}>
                {subcity}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Landmark / Neighborhood</label>
          <input
            type="text"
            placeholder="e.g. Around Edna Mall, Near Total"
            value={formData.location_landmark}
            onChange={(e) => setFormData({ ...formData, location_landmark: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition"
          />
        </div>
      </div>

      {/* Schedule & Preferences */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Schedule & Budget</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-2">Preferred Days *</label>
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
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Time Slot *</label>
            <input
              type="text"
              required
              placeholder="e.g. 4:30 PM - 6:30 PM"
              value={formData.time_slot}
              onChange={(e) => setFormData({ ...formData, time_slot: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Duration *</label>
            <select
              value={formData.session_duration}
              onChange={(e) => setFormData({ ...formData, session_duration: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 bg-white"
            >
              {SESSION_DURATIONS.map((dur) => (
                <option key={dur} value={dur}>{dur}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Budget in ETB (Monthly/Session) *</label>
          <div className="relative">
            <input
              type="number"
              required
              min="100"
              step="50"
              placeholder="4000"
              value={formData.budget_etb}
              onChange={(e) => setFormData({ ...formData, budget_etb: e.target.value })}
              className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 font-semibold"
            />
            <span className="absolute right-3.5 top-2.5 text-xs text-gray-400 font-medium">ETB</span>
          </div>
        </div>
      </div>

      {/* Tutor Preferences */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Tutor Preferences</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Gender Preference</label>
          <div className="grid grid-cols-3 gap-2">
            {["No preference", "Male", "Female"].map((gender) => (
              <button
                key={gender}
                type="button"
                onClick={() => setFormData({ ...formData, preferred_gender: gender })}
                className={`py-2 px-2 text-[11px] rounded-xl font-medium border transition text-center ${
                  formData.preferred_gender === gender
                    ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {gender}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Preferred Experience Level</label>
          <div className="grid grid-cols-3 gap-2">
            {PREFERRED_EXPERIENCES.map((exp) => (
              <button
                key={exp}
                type="button"
                onClick={() => setFormData({ ...formData, preferred_experience: exp })}
                className={`py-2 px-1 text-[11px] rounded-xl font-medium border transition text-center ${
                  formData.preferred_experience === exp
                    ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {exp}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3.5 px-4 rounded-2xl font-bold text-sm bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white shadow-lg shadow-blue-500/25 transition disabled:opacity-60 flex items-center justify-center space-x-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Submitting Request...</span>
          </>
        ) : (
          <span>Find My Tutor Now 🚀</span>
        )}
      </button>
    </form>
  );
}
