import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { getAdminFunnelAnalytics, getAdminAvailabilityMismatch } from '../services/api';

export default function AnalyticsBoard() {
  const [funnel, setFunnel] = useState(null);
  const [mismatch, setMismatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getAdminFunnelAnalytics().catch(() => null),
      getAdminAvailabilityMismatch().catch(() => null),
    ])
      .then(([funnelData, mismatchData]) => {
        if (!active) return;
        setFunnel(funnelData);
        setMismatch(mismatchData);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || 'Failed to load analytics.');
        setLoading(false);
      });

    return () => { active = false; };
  }, []);

  if (loading) {
    return <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading strategic analytics...</span></div>;
  }

  if (error) {
    return <div className="error-state"><span>{error}</span></div>;
  }

  return (
    <div className="analytics-board-view">
      {funnel && (
        <section className="analytics-card">
          <div className="card-header">
            <div>
              <p className="eyebrow">CONVERSION ANALYSIS</p>
              <h2>Tutor Registration Funnel</h2>
            </div>
            <div className="conversion-stats">
              <span>Submission: <strong>{Math.round(funnel.submission_rate * 100)}%</strong></span>
              <span>Approval: <strong>{Math.round(funnel.approval_rate * 100)}%</strong></span>
            </div>
          </div>

          <div className="funnel-steps">
            <div className="funnel-step">
              <span className="step-label">1. Intake Started</span>
              <strong className="step-val">{funnel.started}</strong>
              <div className="funnel-bar"><div className="funnel-fill" style={{ width: '100%' }} /></div>
            </div>
            <div className="funnel-step">
              <span className="step-label">2. Form Submitted</span>
              <strong className="step-val">{funnel.submitted}</strong>
              <div className="funnel-bar">
                <div
                  className="funnel-fill funnel-fill-coral"
                  style={{ width: `${funnel.started ? Math.round((funnel.submitted / funnel.started) * 100) : 0}%` }}
                />
              </div>
            </div>
            <div className="funnel-step">
              <span className="step-label">3. Checklist Approved</span>
              <strong className="step-val">{funnel.approved}</strong>
              <div className="funnel-bar">
                <div
                  className="funnel-fill funnel-fill-green"
                  style={{ width: `${funnel.started ? Math.round((funnel.approved / funnel.started) * 100) : 0}%` }}
                />
              </div>
            </div>
          </div>
        </section>
      )}

      {mismatch && (
        <section className="analytics-card">
          <div className="card-header">
            <div>
              <p className="eyebrow">SUPPLY VS DEMAND</p>
              <h2>Schedule Availability Mismatch</h2>
            </div>
            <div className="card-totals">
              <span>Active Requests: <strong>{mismatch.total_demand}</strong></span>
              <span>Available Tutors: <strong>{mismatch.total_supply}</strong></span>
            </div>
          </div>

          <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Time Slot / Period</th>
                <th>Parent Demand</th>
                <th>Tutor Supply</th>
                <th>Shortage Gap</th>
                <th>Mismatch Ratio</th>
              </tr>
            </thead>
            <tbody>
              {(mismatch.items || []).map((item) => (
                <tr key={item.slot}>
                  <td><strong>{item.slot}</strong></td>
                  <td>{item.demand} req</td>
                  <td>{item.supply} tutors</td>
                  <td>
                    {item.gap > 0 ? (
                      <span className="gap-tag">-{item.gap} shortage</span>
                    ) : (
                      <span className="surplus-tag">Covered</span>
                    )}
                  </td>
                  <td>
                    <div className="ratio-bar-wrapper">
                      <div
                        className="ratio-bar"
                        style={{ width: `${Math.round(item.mismatch_ratio * 100)}%` }}
                      />
                      <span>{Math.round(item.mismatch_ratio * 100)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      )}
    </div>
  );
}
