import React, { useEffect, useState } from 'react';
import { Search, ChevronDown, ChevronUp, Phone, Loader2 } from 'lucide-react';
import { getAdminParents } from '../services/api';

export default function CustomerCRM() {
  const [parents, setParents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [error, setError] = useState(null);

  const fetchParents = (searchTerm = '') => {
    setLoading(true);
    setError(null);
    getAdminParents(searchTerm)
      .then((res) => {
        setParents(res.items || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load parents CRM');
        setLoading(false);
      });
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchParents(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  return (
    <div className="crm-view">
      <div className="ops-header">
        <div>
          <p className="eyebrow">CUSTOMER RELATIONSHIP MANAGEMENT</p>
          <h2>Parent Directory & History</h2>
          <p className="heading-copy">Searchable parent profiles, submission frequency, and matching history.</p>
        </div>
        <div className="search-bar" style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--paper)', border: '1px solid var(--line)', padding: '6px 12px', borderRadius: '12px' }}>
          <Search size={16} color="var(--muted)" />
          <input
            type="text"
            placeholder="Search by parent name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ border: 'none', outline: 'none', background: 'transparent', fontSize: '13px', width: '220px', color: 'var(--ink)' }}
          />
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading parent directory...</span></div>
      ) : error ? (
        <div className="error-state"><span>{error}</span></div>
      ) : parents.length === 0 ? (
        <div className="empty-state" style={{ textAlign: 'center', padding: '40px', background: 'var(--paper)', borderRadius: '16px', border: '1px solid var(--line)' }}>
          <p style={{ color: 'var(--muted)', fontSize: '13px' }}>No parent records found matching "{search}".</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Parent</th>
                <th>Phone</th>
                <th>Total Requests</th>
                <th>Active Pairings</th>
                <th>Registered</th>
                <th>Last Active</th>
                <th>History</th>
              </tr>
            </thead>
            <tbody>
              {parents.map((p) => {
                const isExpanded = expandedId === p.id;
                return (
                  <React.Fragment key={p.id}>
                    <tr>
                      <td>
                        <strong>{p.parent_name}</strong>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>{p.phone_number}</span>
                      </td>
                      <td>
                        <span className="role-tag" style={{ background: 'var(--line)', color: 'var(--ink)' }}>
                          {p.total_requests} requests
                        </span>
                      </td>
                      <td>
                        {p.active_assignments > 0 ? (
                          <span className="role-tag" style={{ background: 'var(--green-soft)', color: 'var(--green)' }}>
                            {p.active_assignments} active
                          </span>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: '12px' }}>—</span>
                        )}
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        {p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        {p.last_active ? new Date(p.last_active).toLocaleDateString() : '—'}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => setExpandedId(isExpanded ? null : p.id)}
                        >
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          <span>{isExpanded ? 'Hide' : 'View'} ({p.requests?.length || 0})</span>
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={7} style={{ background: 'var(--surface-subtle)', padding: '16px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>Request History for {p.parent_name}:</strong>
                            {(p.requests || []).map((req) => (
                              <div
                                key={req.id}
                                style={{
                                  background: 'var(--paper)',
                                  padding: '10px 14px',
                                  borderRadius: '10px',
                                  border: '1px solid var(--line)',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  fontSize: '12px'
                                }}
                              >
                                <div>
                                  <span style={{ fontWeight: 600, color: 'var(--pine)' }}>#{req.id} · {req.student_level}</span>
                                  <span style={{ color: 'var(--muted)', marginLeft: '8px' }}>{(req.subjects || []).join(', ')}</span>
                                  <span style={{ color: 'var(--muted)', marginLeft: '8px' }}>({req.location_subcity})</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  {req.assignment ? (
                                    <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                                      Tutor: {req.assignment.tutor_name}
                                    </span>
                                  ) : (
                                    <span style={{ color: 'var(--muted)' }}>Unassigned</span>
                                  )}
                                  <span className="role-tag">{req.status}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
