import React, { useState, useRef } from 'react';
import { Loader2, AlertCircle, Check, Upload, FileText, X } from 'lucide-react';
import {
  SUBCITIES,
  STUDENT_LEVELS,
  SUBJECTS_LIST,
  EDUCATION_YEARS
} from '../constants/options';
import { TRANSLATIONS } from '../constants/translations';
import { submitTutorRegistration, uploadTutorDocument } from '../services/api';

export default function TutorForm({ user, lang, onSuccess }) {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;
  const formT = t.tutorForm;
  const tVal = t.validation;

  const [formData, setFormData] = useState({
    full_name: user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : '',
    gender: '',
    phone_number: '',
    university: '',
    department: '',
    education_year: '',
    subjects_qualified: [],
    grades_qualified: [],
    years_of_experience: '',
    expected_fee_etb: '',
    base_subcity: '',
    coverage_areas: [],
    availability_schedule: '',
    id_document_url: ''
  });

  const [selectedFile, setSelectedFile] = useState(null);
  const [fileUploadStatus, setFileUploadStatus] = useState(null); // 'uploading' | 'uploaded' | 'error' | null
  const [uploadedFileUrl, setUploadedFileUrl] = useState('');
  const fileInputRef = useRef(null);

  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [globalError, setGlobalError] = useState(null);

  const handleFieldChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const toggleSubject = (subject) => {
    setFormData((prev) => {
      const exists = prev.subjects_qualified.includes(subject);
      const next = exists
        ? prev.subjects_qualified.filter((s) => s !== subject)
        : [...prev.subjects_qualified, subject];
      if (next.length > 0 && errors.subjects_qualified) {
        setErrors((errs) => ({ ...errs, subjects_qualified: null }));
      }
      return { ...prev, subjects_qualified: next };
    });
  };

  const toggleGrade = (grade) => {
    setFormData((prev) => {
      const exists = prev.grades_qualified.includes(grade);
      const next = exists
        ? prev.grades_qualified.filter((g) => g !== grade)
        : [...prev.grades_qualified, grade];
      if (next.length > 0 && errors.grades_qualified) {
        setErrors((errs) => ({ ...errs, grades_qualified: null }));
      }
      return { ...prev, grades_qualified: next };
    });
  };

  const toggleCoverage = (subcity) => {
    setFormData((prev) => {
      const exists = prev.coverage_areas.includes(subcity);
      const next = exists
        ? prev.coverage_areas.filter((c) => c !== subcity)
        : [...prev.coverage_areas, subcity];
      if (next.length > 0 && errors.coverage_areas) {
        setErrors((errs) => ({ ...errs, coverage_areas: null }));
      }
      return { ...prev, coverage_areas: next };
    });
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setFileUploadStatus(null);
      setUploadedFileUrl('');
    }
  };

  const removeSelectedFile = () => {
    setSelectedFile(null);
    setFileUploadStatus(null);
    setUploadedFileUrl('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.full_name.trim()) newErrors.full_name = tVal.required;
    if (!formData.gender) newErrors.gender = tVal.required;
    if (!formData.phone_number.trim()) {
      newErrors.phone_number = tVal.required;
    } else if (formData.phone_number.trim().length < 9) {
      newErrors.phone_number = tVal.phoneInvalid;
    }

    if (!formData.university.trim()) newErrors.university = tVal.required;
    if (!formData.department.trim()) newErrors.department = tVal.required;
    if (!formData.education_year) newErrors.education_year = tVal.required;

    if (formData.subjects_qualified.length === 0) newErrors.subjects_qualified = tVal.atLeastOneSubject;
    if (formData.grades_qualified.length === 0) newErrors.grades_qualified = tVal.atLeastOneGrade;

    if (formData.years_of_experience === '' || isNaN(formData.years_of_experience) || Number(formData.years_of_experience) < 0) {
      newErrors.years_of_experience = tVal.required;
    }

    if (!formData.expected_fee_etb || isNaN(formData.expected_fee_etb) || Number(formData.expected_fee_etb) <= 0) {
      newErrors.expected_fee_etb = tVal.feeMin;
    }

    if (!formData.base_subcity) newErrors.base_subcity = tVal.required;
    if (formData.coverage_areas.length === 0) newErrors.coverage_areas = tVal.atLeastOneCoverage;
    if (!formData.availability_schedule.trim()) newErrors.availability_schedule = tVal.required;

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGlobalError(null);

    if (!validateForm()) {
      setGlobalError(lang === 'am' ? 'እባክዎ በቀይ የተሰመሩትን መረጃዎች በትክክል ይሙሉ' : 'Please fix the highlighted required fields.');
      return;
    }

    setLoading(true);

    try {
      let finalDocUrl = formData.id_document_url.trim();

      // If a file was selected, upload it first
      if (selectedFile && !uploadedFileUrl) {
        setFileUploadStatus('uploading');
        try {
          const uploadRes = await uploadTutorDocument(selectedFile);
          const docUrl = uploadRes.full_url || uploadRes.file_url;
          setUploadedFileUrl(docUrl);
          setFileUploadStatus('uploaded');
          
          if (finalDocUrl) {
            finalDocUrl = `${docUrl} | ${finalDocUrl}`;
          } else {
            finalDocUrl = docUrl;
          }
        } catch (uploadErr) {
          setFileUploadStatus('error');
          console.warn('Document upload error, proceeding with URL if available:', uploadErr);
        }
      } else if (uploadedFileUrl) {
        finalDocUrl = finalDocUrl ? `${uploadedFileUrl} | ${finalDocUrl}` : uploadedFileUrl;
      }

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
        id_document_url: finalDocUrl || null
      };

      const result = await submitTutorRegistration(payload);
      onSuccess(result, 'tutor');
    } catch (err) {
      setGlobalError(err.message || 'Failed to register profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="px-4 pb-12 space-y-5">
      {globalError && (
        <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-2xl flex items-start space-x-2.5 animate-in fade-in">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <span className="leading-relaxed whitespace-pre-line font-medium">{globalError}</span>
        </div>
      )}

      {/* 1. Basic Personal Info */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{formT.sectionProfile}</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.fullName} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder={formT.fullNamePlaceholder}
            value={formData.full_name}
            onChange={(e) => handleFieldChange('full_name', e.target.value)}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition ${
              errors.full_name
                ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                : 'border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100'
            }`}
          />
          {errors.full_name && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.full_name}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">
              {formT.gender} <span className="text-red-500">*</span>
            </label>
            <div className={`grid grid-cols-2 gap-2 p-0.5 rounded-xl ${errors.gender ? 'border border-red-500 bg-red-50/20 p-1' : ''}`}>
              {['Male', 'Female'].map((genderOption) => {
                const label = genderOption === 'Male' ? t.options.male : t.options.female;
                const selected = formData.gender === genderOption;
                return (
                  <button
                    key={genderOption}
                    type="button"
                    onClick={() => handleFieldChange('gender', genderOption)}
                    className={`py-2 px-2 text-xs rounded-xl font-medium border text-center transition cursor-pointer ${
                      selected
                        ? 'border-blue-500 bg-blue-50 text-blue-700 font-semibold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            {errors.gender && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.gender}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              {formT.activePhone} <span className="text-red-500">*</span>
            </label>
            <input
              type="tel"
              placeholder={formT.phonePlaceholder}
              value={formData.phone_number}
              onChange={(e) => handleFieldChange('phone_number', e.target.value)}
              className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition ${
                errors.phone_number
                  ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                  : 'border-gray-200 focus:outline-none focus:border-blue-500'
              }`}
            />
            {errors.phone_number && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.phone_number}</p>}
          </div>
        </div>
      </div>

      {/* 2. Academic Background */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-3.5">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{formT.sectionAcademic}</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.university} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder={formT.universityPlaceholder}
            value={formData.university}
            onChange={(e) => handleFieldChange('university', e.target.value)}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition ${
              errors.university
                ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                : 'border-gray-200 focus:outline-none focus:border-blue-500'
            }`}
          />
          {errors.university && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.university}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              {formT.department} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              placeholder={formT.departmentPlaceholder}
              value={formData.department}
              onChange={(e) => handleFieldChange('department', e.target.value)}
              className={`w-full text-xs px-3 py-2.5 rounded-xl border transition ${
                errors.department
                  ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                  : 'border-gray-200 focus:outline-none focus:border-blue-500'
              }`}
            />
            {errors.department && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.department}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              {formT.yearStatus} <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.education_year}
              onChange={(e) => handleFieldChange('education_year', e.target.value)}
              className={`w-full text-xs px-3 py-2.5 rounded-xl border bg-white transition cursor-pointer ${
                errors.education_year
                  ? 'border-red-500 bg-red-50/20 text-red-900 focus:ring-1 focus:ring-red-500'
                  : 'border-gray-200 focus:outline-none focus:border-blue-500 text-gray-700'
              }`}
            >
              <option value="">{formT.selectYearPlaceholder}</option>
              {EDUCATION_YEARS.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
            {errors.education_year && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.education_year}</p>}
          </div>
        </div>
      </div>

      {/* 3. Teaching Qualifications */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{formT.sectionQualifications}</h2>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">
              {formT.subjectsQualified} <span className="text-red-500">*</span>
            </label>
            <span className="text-[11px] text-blue-600 font-medium">
              {formData.subjects_qualified.length} {formT.subjectsSelected}
            </span>
          </div>
          <div className={`flex flex-wrap gap-1.5 p-2 rounded-xl border transition ${
            errors.subjects_qualified ? 'border-red-500 bg-red-50/10' : 'border-gray-100'
          }`}>
            {SUBJECTS_LIST.map((subject) => {
              const selected = formData.subjects_qualified.includes(subject);
              return (
                <button
                  key={subject}
                  type="button"
                  onClick={() => toggleSubject(subject)}
                  className={`py-1.5 px-3 rounded-full text-xs font-medium transition flex items-center space-x-1 cursor-pointer ${
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
          {errors.subjects_qualified && (
            <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.subjects_qualified}</p>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">
              {formT.targetGrades} <span className="text-red-500">*</span>
            </label>
            <span className="text-[11px] text-blue-600 font-medium">
              {formData.grades_qualified.length} {formT.gradesSelected}
            </span>
          </div>
          <div className={`grid grid-cols-2 sm:grid-cols-3 gap-2 p-2 rounded-xl border transition ${
            errors.grades_qualified ? 'border-red-500 bg-red-50/10' : 'border-gray-100'
          }`}>
            {STUDENT_LEVELS.map((level) => {
              const selected = formData.grades_qualified.includes(level);
              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => toggleGrade(level)}
                  className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-left transition cursor-pointer ${
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
          {errors.grades_qualified && (
            <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.grades_qualified}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 pt-1">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              {formT.experienceYears} <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="0"
              step="0.5"
              placeholder="e.g. 2"
              value={formData.years_of_experience}
              onChange={(e) => handleFieldChange('years_of_experience', e.target.value)}
              className={`w-full text-xs px-3 py-2.5 rounded-xl border transition ${
                errors.years_of_experience
                  ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                  : 'border-gray-200 focus:outline-none focus:border-blue-500'
              }`}
            />
            {errors.years_of_experience && (
              <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.years_of_experience}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              {formT.expectedFeePerHour} <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="100"
              step="50"
              placeholder={formT.feePlaceholder}
              value={formData.expected_fee_etb}
              onChange={(e) => handleFieldChange('expected_fee_etb', e.target.value)}
              className={`w-full text-xs px-3 py-2.5 rounded-xl border font-semibold transition ${
                errors.expected_fee_etb
                  ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500 text-red-900'
                  : 'border-gray-200 focus:outline-none focus:border-blue-500 text-gray-900'
              }`}
            />
            {errors.expected_fee_etb && (
              <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.expected_fee_etb}</p>
            )}
          </div>
        </div>
      </div>

      {/* 4. Location & Coverage */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{formT.sectionLocation}</h2>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.baseSubcity} <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.base_subcity}
            onChange={(e) => handleFieldChange('base_subcity', e.target.value)}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border bg-white transition cursor-pointer font-medium ${
              errors.base_subcity
                ? 'border-red-500 bg-red-50/20 text-red-900 focus:ring-1 focus:ring-red-500'
                : 'border-gray-200 focus:outline-none focus:border-blue-500 text-gray-700'
            }`}
          >
            <option value="">{formT.selectBaseSubcityPlaceholder}</option>
            {SUBCITIES.map((subcity) => (
              <option key={subcity} value={subcity}>{subcity}</option>
            ))}
          </select>
          {errors.base_subcity && <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.base_subcity}</p>}
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-700">
              {formT.coverageAreas} <span className="text-red-500">*</span>
            </label>
            <span className="text-[11px] text-blue-600 font-medium">
              {formData.coverage_areas.length} {formT.coverageSelected}
            </span>
          </div>
          <div className={`flex flex-wrap gap-1.5 p-2 rounded-xl border transition ${
            errors.coverage_areas ? 'border-red-500 bg-red-50/10' : 'border-gray-100'
          }`}>
            {SUBCITIES.map((subcity) => {
              const selected = formData.coverage_areas.includes(subcity);
              return (
                <button
                  key={subcity}
                  type="button"
                  onClick={() => toggleCoverage(subcity)}
                  className={`py-1.5 px-2.5 rounded-xl text-[11px] font-medium transition cursor-pointer ${
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
          {errors.coverage_areas && (
            <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.coverage_areas}</p>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.availability} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder={formT.availabilityPlaceholder}
            value={formData.availability_schedule}
            onChange={(e) => handleFieldChange('availability_schedule', e.target.value)}
            className={`w-full text-xs px-3.5 py-2.5 rounded-xl border transition ${
              errors.availability_schedule
                ? 'border-red-500 bg-red-50/20 focus:ring-1 focus:ring-red-500'
                : 'border-gray-200 focus:outline-none focus:border-blue-500'
            }`}
          />
          {errors.availability_schedule && (
            <p className="text-red-600 text-[11px] mt-1 font-medium">{errors.availability_schedule}</p>
          )}
        </div>
      </div>

      {/* 5. Dual Document Upload (File + Portfolio URL) */}
      <div className="bg-white p-4 rounded-2xl shadow-xs border border-gray-100 space-y-4">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">{formT.sectionDocuments}</h2>

        {/* File Upload for ID / CV */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.uploadDocument}
          </label>
          <p className="text-[11px] text-gray-400 mb-2">{formT.uploadHint}</p>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
            className="hidden"
            id="tutor-doc-file"
          />

          {!selectedFile ? (
            <label
              htmlFor="tutor-doc-file"
              className="flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-200 hover:border-blue-400 rounded-2xl cursor-pointer bg-gray-50/50 hover:bg-blue-50/30 transition group"
            >
              <Upload className="w-6 h-6 text-gray-400 group-hover:text-blue-500 mb-1.5 transition" />
              <span className="text-xs font-semibold text-blue-600 group-hover:text-blue-700">
                {formT.chooseFile}
              </span>
            </label>
          ) : (
            <div className="flex items-center justify-between p-3 bg-blue-50/70 border border-blue-200 rounded-xl">
              <div className="flex items-center space-x-2 truncate">
                <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                <span className="text-xs text-blue-900 font-medium truncate">
                  {selectedFile.name} ({(selectedFile.size / 1024).toFixed(0)} KB)
                </span>
              </div>
              <button
                type="button"
                onClick={removeSelectedFile}
                className="p-1 hover:bg-blue-200/60 rounded-lg text-blue-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Portfolio / Google Drive URL */}
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1">
            {formT.documentUrl}
          </label>
          <input
            type="url"
            placeholder={formT.documentUrlPlaceholder}
            value={formData.id_document_url}
            onChange={(e) => handleFieldChange('id_document_url', e.target.value)}
            className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3.5 px-4 rounded-2xl font-bold text-sm bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white shadow-lg shadow-blue-500/25 transition disabled:opacity-60 flex items-center justify-center space-x-2 cursor-pointer"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>{formT.submittingBtn}</span>
          </>
        ) : (
          <span>{formT.submitBtn}</span>
        )}
      </button>
    </form>
  );
}
