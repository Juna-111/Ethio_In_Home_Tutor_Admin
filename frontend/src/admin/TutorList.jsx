import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, AlertCircle, Loader2, Search } from 'lucide-react';
import { getAdminTutors } from '../services/api';

const PAGE_SIZE = 20;

export default function TutorList({ onSelectTutor }) {
  const [tutors, setTutors] = useState([]);
  const [list, setList] = useState({ total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAdminTutors({ status: statusFilter || undefined, search: search || undefined, page, page_size: PAGE_SIZE })
      .then((data) => {
        setTutors(data.items || []);
        setList({ total: data.total || 0, page: data.page || page, page_size: data.page_size || PAGE_SIZE });
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load tutors.');
        setLoading(false);
      });
  }, [statusFilter, search, page]);

  const totalPages = Math.max(1, Math.ceil(list.total / list.page_size));

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
              onClick={() => { setStatusFilter(id); setPage(1); }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="search-field">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search name or phone…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            aria-label="Search tutors by name or phone number"
          />
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading tutors...</span></div>
      ) : error ? (
        <div className="error-state"><AlertCircle size={20} /><span>{error}</span></div>
      ) : tutors.length === 0 ? (
        <div className="empty-state">
          No tutors found{search ? ` matching "${search}"` : ''} for status: {statusFilter || 'all'}.
        </div>
      ) : (
        <>
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
          <div className="pagination-row">
            <span>{list.total ? `${(list.page - 1) * list.page_size + 1}–${Math.min(list.page * list.page_size, list.total)} of ${list.total}` : '0 tutors'}</span>
            <div>
              <button className="icon-button" type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={16} /></button>
              <span>Page {page} / {totalPages}</span>
              <button className="icon-button" type="button" aria-label="Next page" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}><ChevronRight size={16} /></button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
