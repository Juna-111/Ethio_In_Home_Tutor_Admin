import React, { useEffect, useState } from 'react';
import { Play, Loader2 } from 'lucide-react';
import { getAdminFlags, getAdminIncidents, updateAdminIncident, runAdminCron } from '../services/api';

export default function OpsQueue({ onSelectTutor }) {
  const [flags, setFlags] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [activeTab, setActiveTab] = useState('flags');
  const [loading, setLoading] = useState(true);
  const [cronRunning, setCronRunning] = useState(false);
  const [cronResult, setCronResult] = useState(null);
  const [error, setError] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      getAdminFlags().catch(() => []),
      getAdminIncidents({ page: 1, page_size: 50 }).catch(() => ({ items: [] })),
    ])
      .then(([flagsData, incidentsData]) => {
        setFlags(flagsData || []);
        setIncidents(incidentsData.items || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load ops queue.');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleResolveIncident = async (incidentId) => {
    try {
      await updateAdminIncident(incidentId, { status: 'resolved' });
      setIncidents((prev) =>
        prev.map((i) => (i.id === incidentId ? { ...i, status: 'resolved' } : i))
      );
    } catch (err) {
      alert(`Could not resolve incident: ${err.message}`);
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
            Incidents ({incidents.length})
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

      {cronResult && (
        <div className="cron-banner">
          <span>{cronResult}</span>
        </div>
      )}

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading operations queue...</span></div>
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
                    <button className="row-action-btn" type="button" onClick={() => handleResolveIncident(inc.id)}>
                      Resolve
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
      )}
    </div>
  );
}
