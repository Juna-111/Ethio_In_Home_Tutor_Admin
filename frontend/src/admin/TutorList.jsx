import React, { useEffect, useState } from 'react';
import { Search, Filter, GraduationCap, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
import { getAdminTutors } from '../services/api';

export default function TutorList({ onSelectTutor }) {
  const [tutors, setTutors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState(null);

  const fetchTutors = () => {
    setLoading(true);
    setError(null);
    getAdminTutors({ status: statusFilter || undefined, page: 1, page_size: 50 })
      .then((data) => {
        setTutors(data.items || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load tutors.');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTutors();
  }, [statusFilter]);

  return (
    <div className="tutor-list-view">
      <div className="filter-bar">
        <div className="status-pill-group">
          {[
            { id: '', label: 'All Tutors' },
            { id: 'pending', label: 'Pending' },
            { id: 'verified', label: 'Verified' },
            { id: 'probation', label: 'Probation' },
            { id: 'rejected', label: 'Rejected' },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={statusFilter === id ? 'pill-active' : 'pill'}
              onClick={() => setStatusFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading tutors...</span></div>
      ) : error ? (
        <div className="error-state"><AlertCircle size={20} /><span>{error}</span></div>
      ) : tutors.length === 0 ? (
        <div className="empty-state">No tutors found for status: {statusFilter || 'all'}.</div>
      ) : (
        <div className="tutors-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tutor Name</th>
                <th>Base Subcity</th>
                <th>Subjects</th>
                <th>Entrance</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tutors.map((t) => (
                <tr key={t.id} onClick={() => onSelectTutor(t.id)} className="clickable-row">
                  <td>#{t.id}</td>
                  <td><strong>{t.full_name}</strong><br /><small>{t.phone_number}</small></td>
                  <td>{t.base_subcity}</td>
                  <td>{(t.subjects_qualified || []).slice(0, 3).join(', ')}</td>
                  <td>{t.entrance_result ?? '—'}</td>
                  <td>
                    <span className={`status-badge status-${t.status}`}>
                      {t.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <button className="row-action-btn" type="button" onClick={(e) => { e.stopPropagation(); onSelectTutor(t.id); }}>
                      Review <ChevronRight size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
