import React, { useEffect, useState } from 'react';
import { GitPullRequest, Clock, Loader2, AlertCircle, Calendar } from 'lucide-react';
import { getAdminAssignmentPipeline } from '../services/api';

const STATUS_CONFIG = {
  pending: { label: 'Requests Received', tone: 'coral' },
  reviewing: { label: 'Under Review', tone: 'citrus' },
  matched: { label: 'Active Matched', tone: 'green' },
  closed: { label: 'Closed / Filled', tone: 'blue' },
};

export default function AssignmentPipeline() {
  const [pipeline, setPipeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPipeline = () => {
    setLoading(true);
    setError(null);
    getAdminAssignmentPipeline()
      .then((res) => {
        setPipeline(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load assignment pipeline');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchPipeline();
  }, []);

  const statuses = ['pending', 'reviewing', 'matched', 'closed'];

  return (
    <div className="pipeline-view">
      <div className="ops-header">
        <div>
          <p className="eyebrow">OPERATIONAL VELOCITY</p>
          <h2>Assignment Pipeline & Turnaround</h2>
          <p className="heading-copy">Pipeline status counts, median days to action, and oldest requests per stage.</p>
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading assignment pipeline...</span></div>
      ) : error ? (
        <div className="error-state"><span>{error}</span></div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Status Counts & Median Age Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
            {statuses.map((st) => {
              const cfg = STATUS_CONFIG[st] || { label: st, tone: 'blue' };
              const count = pipeline?.status_counts?.[st] || 0;
              const medianDays = pipeline?.median_age_days?.[st] ?? 0;
              return (
                <article key={st} className={`metric metric-${cfg.tone}`}>
                  <div className="metric-topline">
                    <span>{cfg.label}</span>
                    <GitPullRequest size={18} strokeWidth={1.8} />
                  </div>
                  <strong>{count}</strong>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} />
                    <span>Median age: <strong>{medianDays} days</strong></span>
                  </div>
                  <span className="metric-rule" />
                </article>
              );
            })}
          </div>

          {/* Oldest Requests Per Status */}
          <div style={{ background: 'var(--paper)', borderRadius: '16px', border: '1px solid var(--line)', padding: '20px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--ink)', marginBottom: '14px' }}>
              Oldest Requests Awaiting Action (Bottleneck Detection)
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
              {statuses.filter((st) => st !== 'closed').map((st) => {
                const items = pipeline?.oldest_per_status?.[st] || [];
                const cfg = STATUS_CONFIG[st] || { label: st };
                return (
                  <div key={st} style={{ background: 'var(--surface-subtle)', borderRadius: '12px', padding: '12px', border: '1px solid var(--line)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>{cfg.label}</strong>
                      <span className="role-tag" style={{ fontSize: '10px' }}>{items.length} oldest</span>
                    </div>
                    {items.length === 0 ? (
                      <p style={{ fontSize: '11px', color: 'var(--muted)', margin: '8px 0' }}>No requests in this stage.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {items.map((req) => (
                          <div
                            key={req.id}
                            style={{
                              background: 'var(--paper)',
                              padding: '8px 10px',
                              borderRadius: '8px',
                              border: '1px solid var(--line)',
                              fontSize: '11px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}
                          >
                            <div>
                              <strong style={{ color: 'var(--pine)' }}>#{req.id}</strong> {req.parent_name} ({req.location_subcity})
                            </div>
                            <span style={{ color: 'var(--coral)', fontWeight: 700 }}>
                              {req.age_days}d ago
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
