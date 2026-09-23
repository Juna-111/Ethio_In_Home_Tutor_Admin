import React, { useState } from 'react';
import { Loader2, AlertCircle, Check } from 'lucide-react';
import {
  SUBCITIES,
  STUDENT_LEVELS,
  SUBJECTS_LIST,
  EDUCATION_YEARS
} from '../constants/options';
import { submitTutorRegistration } from '../services/api';

export default function TutorForm({ user, onSuccess }) {
  const [formData, setFormData] = useState({
    full_name: user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : '',
    gender: 'Male',
    phone_number: '',
    university: 'Addis Ababa University (AAU)',
    department: 'Software Engineering',
    education_year: '4th Year',
    subjects_qualified: ['Maths', 'Physics'],
    grades_qualified: ['High School 9-10', 'Prep 11-12'],
    years_of_experience: 2.0,
    expected_fee_etb: 400,
    base_subcity: 'Bole',
    coverage_areas: ['Bole', 'Yeka'],
    availability_schedule: 'Weekdays after 5:00 PM, Weekends all day',
    id_document_url: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggleSubject = (subject) => {
    setFormData((prev) => {
      const exists = prev.subjects_qualified.includes(subject);
      if (exists) {
        if (prev.subjects_qualified.length <= 1) return prev;
        return {
          ...prev,
          subjects_qualified: prev.subjects_qualified.filter((s) => s !== subject)
        };
      } else {
        return { ...prev, subjects_qualified: [...prev.subjects_qualified, subject] };
      }
    });
  };

  const toggleGrade = (grade) => {
    setFormData((prev) => {
      const exists = prev.grades_qualified.includes(grade);
      if (exists) {
        if (prev.grades_qualified.length <= 1) return prev;
        return {
          ...prev,
          grades_qualified: prev.grades_qualified.filter((g) => g !== grade)
        };
      } else {
        return { ...prev, grades_qualified: [...prev.grades_qualified, grade] };
      }
    });
  };

  const toggleCoverage = (subcity) => {
    setFormData((prev) => {
      const exists = prev.coverage_areas.includes(subcity);
      if (exists) {
        if (prev.coverage_areas.length <= 1) return prev;
        return {
          ...prev,
          coverage_areas: prev.coverage_areas.filter((c) => c !== subcity)
        };
      } else {
        return { ...prev, coverage_areas: [...prev.coverage_areas, subcity] };
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.full_name.trim()) {
      setError("Please enter your full legal name.");
      return;
    }
    if (!formData.phone_number.trim() || formData.phone_number.length < 9) {
      setError("Please enter a valid active phone number.");
      return;
    }
    if (!formData.university.trim()) {
      setError("Please enter your university name.");
      return;
    }
    if (!formData.department.trim()) {
      setError("Please enter your department or major.");
      return;
    }
    if (formData.subjects_qualified.length === 0) {
      setError("Please select at least one subject you can teach.");
      return;
    }
    if (formData.grades_qualified.length === 0) {
      setError("Please select at least one grade level you are qualified for.");
      return;
    }
    if (formData.coverage_areas.length === 0) {
      setError("Please select at least one sub-city in your coverage area.");
      return;
    }
    if (!formData.expected_fee_etb || Number(formData.expected_fee_etb) <= 0) {
      setError("Please enter your expected tutoring fee in ETB.");
      return;
    }

    setLoading(true);

    try {
      const payload = {
        telegram_user_id: user?.id || null,
        full_name: formData.full_name.trim(),
        gender: formData.gender,
        phone_number: formData.phone_number.trim(),
        university: formData.university.trim(),
        department: formData.department.trim(),
        education_year: formData.education_year,
        subjects_qualified: formData.subjects_qualified,
        grades_qualified: formData.grades_qualified,
        years_of_experience: parseFloat(formData.years_of_experience) || 0.0,
        expected_fee_etb: parseFloat(formData.expected_fee_etb),
        base_subcity: formData.base_subcity,
        coverage_areas: formData.coverage_areas,
        availability_schedule: formData.availability_schedule.trim(),
        id_document_url: formData.id_document_url.trim() || null
      };

      const result = await submitTutorRegistration(payload);
      onSuccess(result, 'tutor');
    } catch (err) {
      setError(err.message || "Failed to register profile. Please try again.");
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

      {/* Basic Personal Info */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Tutor Profile</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Full Legal Name *</label>
          <input
            type="text"
            required
            placeholder="e.g. Sara Tadesse"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">Gender *</label>
            <div className="grid grid-cols-2 gap-2">
              {["Male", "Female"].map((gender) => (
                <button
                  key={gender}
                  type="button"
                  onClick={() => setFormData({ ...formData, gender })}
                  className={`py-2 px-2 text-xs rounded-xl font-medium border text-center transition ${
                    formData.gender === gender
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
            <label className="block text-xs font-semibold text-gray-700 mb-1">Active Phone *</label>
            <input
              type="tel"
              required
              placeholder="0911223344"
              value={formData.phone_number}
              onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Academic Background */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Academic Background</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">University / College *</label>
          <input
            type="text"
            required
            placeholder="e.g. Addis Ababa University (AAiT)"
            value={formData.university}
            onChange={(e) => setFormData({ ...formData, university: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Department / Major *</label>
            <input
              type="text"
              required
              placeholder="e.g. Computer Science"
              value={formData.department}
              onChange={(e) => setFormData({ ...formData, department: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Year / Status *</label>
            <select
              value={formData.education_year}
              onChange={(e) => setFormData({ ...formData, education_year: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 bg-white"
            >
              {EDUCATION_YEARS.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Qualifications */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Teaching Qualifications</h2>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">Subjects Qualified to Teach *</label>
            <span className="text-[11px] text-blue-600 font-medium">{formData.subjects_qualified.length} selected</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SUBJECTS_LIST.map((subject) => {
              const selected = formData.subjects_qualified.includes(subject);
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

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">Target Grade Levels *</label>
            <span className="text-[11px] text-blue-600 font-medium">{formData.grades_qualified.length} selected</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {STUDENT_LEVELS.map((level) => {
              const selected = formData.grades_qualified.includes(level);
              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => toggleGrade(level)}
                  className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-left transition ${
                    selected
                      ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {level}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Experience (Years) *</label>
            <input
              type="number"
              min="0"
              step="0.5"
              value={formData.years_of_experience}
              onChange={(e) => setFormData({ ...formData, years_of_experience: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Expected Fee (ETB) *</label>
            <input
              type="number"
              min="100"
              step="50"
              placeholder="350"
              value={formData.expected_fee_etb}
              onChange={(e) => setFormData({ ...formData, expected_fee_etb: e.target.value })}
              className="w-full text-xs px-3 py-2 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 font-semibold"
            />
          </div>
        </div>
      </div>

      {/* Location & Coverage */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Location & Coverage Areas</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Where do you live? (Base Sub-City) *</label>
          <select
            value={formData.base_subcity}
            onChange={(e) => setFormData({ ...formData, base_subcity: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 bg-white font-medium"
          >
            {SUBCITIES.map((subcity) => (
              <option key={subcity} value={subcity}>{subcity}</option>
            ))}
          </select>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">Sub-Cities Willing to Travel To *</label>
            <span className="text-[11px] text-blue-600 font-medium">{formData.coverage_areas.length} selected</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SUBCITIES.map((subcity) => {
              const selected = formData.coverage_areas.includes(subcity);
              return (
                <button
                  key={subcity}
                  type="button"
                  onClick={() => toggleCoverage(subcity)}
                  className={`py-1.5 px-2.5 rounded-xl text-[11px] font-medium transition ${
                    selected
                      ? 'bg-blue-600 text-white shadow-xs font-semibold'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {subcity}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">Availability Schedule *</label>
          <input
            type="text"
            required
            placeholder="e.g. Weekdays after 5 PM, Weekends all day"
            value={formData.availability_schedule}
            onChange={(e) => setFormData({ ...formData, availability_schedule: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">ID Document / Certificate URL (Optional)</label>
          <input
            type="url"
            placeholder="https://..."
            value={formData.id_document_url}
            onChange={(e) => setFormData({ ...formData, id_document_url: e.target.value })}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
          />
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
            <span>Submitting Profile...</span>
          </>
        ) : (
          <span>Register as Tutor 🎓</span>
        )}
      </button>
    </form>
  );
}
