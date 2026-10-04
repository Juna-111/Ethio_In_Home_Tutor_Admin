import React, { useEffect, useState } from 'react';
import { Play, Loader2, ChevronLeft, ChevronRight, AlertCircle } from 'lucide-react';
import { getAdminFlags, getAdminIncidents, updateAdminIncident, runAdminCron } from '../services/api';

const INCIDENT_PAGE_SIZE = 20;

export default function OpsQueue({ onSelectTutor }) {
  const [flags, setFlags] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [incidentTotal, setIncidentTotal] = useState(0);
  const [incidentPage, setIncidentPage] = useState(1);
  const [activeTab, setActiveTab] = useState('flags');
  const [loading, setLoading] = useState(true);
  const [cronRunning, setCronRunning] = useState(false);
  const [cronResult, setCronResult] = useState(null);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [resolvingId, setResolvingId] = useState(null);

  const loadData = (page = incidentPage) => {
    setLoading(true);
    setError(null);
    // Surface real failures instead of silently rendering "nothing found":
    // an empty list caused by a network/auth error looks identical to a
    // genuinely empty queue, which hides problems from the admin.
    Promise.all([
      getAdminFlags(),
      getAdminIncidents({ page, page_size: INCIDENT_PAGE_SIZE }),
    ])
      .then(([flagsData, incidentsData]) => {
        setFlags(flagsData || []);
        setIncidents(incidentsData.items || []);
        setIncidentTotal(incidentsData.total || 0);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load ops queue.');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData(1);
  }, []);

  useEffect(() => {
    if (activeTab === 'incidents') loadData(incidentPage);
  }, [incidentPage]);

  const incidentTotalPages = Math.max(1, Math.ceil(incidentTotal / INCIDENT_PAGE_SIZE));

  const handleResolveIncident = async (incidentId) => {
    setActionError(null);
    setResolvingId(incidentId);
    try {
      await updateAdminIncident(incidentId, { status: 'resolved' });
      setIncidents((prev) =>
        prev.map((i) => (i.id === incidentId ? { ...i, status: 'resolved' } : i))
      );
    } catch (err) {
      setActionError(err.message || 'Could not resolve incident.');
    } finally {
      setResolvingId(null);
    }
  };

  const handleRunCron = async () => {
    setCronRunning(true);
    setCronResult(null);
    try {
      const res = await runAdminCron();
      setCronResult(`Success: Claimed ${res.claimed_events} events, dispatched ${res.sent_notifications} alerts.`);
      loadData();
    } catch (err) {
      setCronResult(`Cron failed: ${err.message}`);
    } finally {
      setCronRunning(false);
    }
  };

  return (
    <div className="ops-queue-view">
      <div className="ops-header">
        <div className="status-pill-group">
          <button
            type="button"
            className={activeTab === 'flags' ? 'pill-active' : 'pill'}
            onClick={() => setActiveTab('flags')}
          >
            Red Flags ({flags.length})
          </button>
          <button
            type="button"
            className={activeTab === 'incidents' ? 'pill-active' : 'pill'}
            onClick={() => setActiveTab('incidents')}
          >
            Incidents ({incidentTotal})
          </button>
        </div>

        <button
          className="btn-secondary"
          type="button"
          onClick={handleRunCron}
          disabled={cronRunning}
        >
          {cronRunning ? <Loader2 className="spin" size={15} /> : <Play size={15} />}
          <span>Run Scheduled Checks</span>
        </button>
      </div>

      {actionError && <div className="inline-message inline-error" role="alert"><AlertCircle size={14} />{actionError}</div>}

      {cronResult && (
        <div className="cron-banner">
          <span>{cronResult}</span>
        </div>
      )}

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading operations queue...</span></div>
      ) : error ? (
        <div className="error-state"><AlertCircle size={20} /><span>{error}</span></div>
      ) : activeTab === 'flags' ? (
        flags.length === 0 ? (
          <div className="empty-state">No active red flags detected across tutor profiles!</div>
        ) : (
          <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Tutor</th>
                <th>Flag Type</th>
                <th>Detail</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={`${f.tutor_id}-${f.flag_type}`}>
                  <td>
                    <span className={`flag-badge flag-${f.severity}`}>
                      {f.severity.toUpperCase()}
                    </span>
                  </td>
                  <td><strong>{f.tutor_name}</strong><br /><small>ID #{f.tutor_id}</small></td>
                  <td><code>{f.flag_type}</code></td>
                  <td>{f.detail}</td>
                  <td>
                    <button className="row-action-btn" type="button" onClick={() => onSelectTutor(f.tutor_id)}>
                      Review Tutor
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )
      ) : incidents.length === 0 ? (
        <div className="empty-state">No incidents logged.</div>
      ) : (
        <>
        <div className="table-scroll">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Tutor ID</th>
              <th>Severity</th>
              <th>Description</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc) => (
              <tr key={inc.id}>
                <td>#{inc.id}</td>
                <td>
                  <button className="link-btn" type="button" onClick={() => onSelectTutor(inc.tutor_id)}>
                    Tutor #{inc.tutor_id}
                  </button>
                </td>
                <td>
                  <span className={`flag-badge flag-${inc.severity}`}>
                    {inc.severity.toUpperCase()}
                  </span>
                </td>
                <td>{inc.description}</td>
                <td>
                  <span className={`status-badge status-${inc.status}`}>
                    {inc.status.toUpperCase()}
                  </span>
                </td>
                <td>
                  {inc.status !== 'resolved' ? (
                    <button className="row-action-btn" type="button" onClick={() => handleResolveIncident(inc.id)}
                      disabled={resolvingId === inc.id}
                    >
                      {resolvingId === inc.id ? 'Resolving…' : 'Resolve'}
                    </button>
                  ) : (
                    <small className="text-muted">Resolved</small>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <div className="pagination-row">
          <span>{incidentTotal ? `${(incidentPage - 1) * INCIDENT_PAGE_SIZE + 1}–${Math.min(incidentPage * INCIDENT_PAGE_SIZE, incidentTotal)} of ${incidentTotal}` : '0 incidents'}</span>
          <div>
            <button className="icon-button" type="button" aria-label="Previous page" disabled={incidentPage <= 1} onClick={() => setIncidentPage((p) => p - 1)}><ChevronLeft size={16} /></button>
            <span>Page {incidentPage} / {incidentTotalPages}</span>
            <button className="icon-button" type="button" aria-label="Next page" disabled={incidentPage >= incidentTotalPages} onClick={() => setIncidentPage((p) => p + 1)}><ChevronRight size={16} /></button>
          </div>
        </div>
        </>
      )}
    </div>
  );
}
