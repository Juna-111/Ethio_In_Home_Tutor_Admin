import React, { useEffect, useState } from 'react';
import { Shield, UserPlus, Trash2, History, AlertCircle, Loader2 } from 'lucide-react';
import { getAdminUsers, createAdminUser, deleteAdminUser, getAdminAuditLog } from '../services/api';

export default function AdminManagement() {
  const [admins, setAdmins] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('admins');
  const [newTelegramId, setNewTelegramId] = useState('');
  const [newRole, setNewRole] = useState('verifier');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      getAdminUsers().catch((err) => ({ items: [], error: err })),
      getAdminAuditLog({ page: 1, page_size: 50 }).catch((err) => ({ items: [], error: err })),
    ])
      .then(([adminsData, auditData]) => {
        setAdmins(adminsData.items || []);
        setAuditLogs(auditData.items || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load admin management.');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddAdmin = async (e) => {
    e.preventDefault();
    if (!newTelegramId.trim()) return;
    try {
      await createAdminUser({ telegram_id: Number(newTelegramId.trim()), role: newRole });
      setNewTelegramId('');
      loadData();
    } catch (err) {
      alert(`Could not add admin: ${err.message}`);
    }
  };

  const handleDeleteAdmin = async (telegramId) => {
    if (!window.confirm(`Are you sure you want to remove admin ${telegramId}?`)) return;
    try {
      await deleteAdminUser(telegramId);
      loadData();
    } catch (err) {
      alert(`Could not remove admin: ${err.message}`);
    }
  };

  return (
    <div className="admin-mgmt-view">
      <div className="ops-header">
        <div className="status-pill-group">
          <button
            type="button"
            className={activeTab === 'admins' ? 'pill-active' : 'pill'}
            onClick={() => setActiveTab('admins')}
          >
            Admin Users ({admins.length})
          </button>
          <button
            type="button"
            className={activeTab === 'audit' ? 'pill-active' : 'pill'}
            onClick={() => setActiveTab('audit')}
          >
            Audit Trail ({auditLogs.length})
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><Loader2 className="spin" size={24} /><span>Loading admin settings...</span></div>
      ) : error ? (
        <div className="error-state"><span>{error}</span></div>
      ) : activeTab === 'admins' ? (
        <div>
          <form className="add-admin-form" onSubmit={handleAddAdmin}>
            <input
              type="number"
              placeholder="Telegram ID (e.g. 123456789)"
              value={newTelegramId}
              onChange={(e) => setNewTelegramId(e.target.value)}
              required
            />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
              <option value="verifier">Verifier</option>
              <option value="matcher">Matcher</option>
              <option value="admin">General Admin</option>
              <option value="super_admin">Super Admin</option>
            </select>
            <button className="btn-primary" type="submit">
              <UserPlus size={16} />
              <span>Add Admin</span>
            </button>
          </form>

          <table className="admin-table">
            <thead>
              <tr>
                <th>Telegram ID</th>
                <th>Role</th>
                <th>Status</th>
                <th>Added By</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((adm) => (
                <tr key={adm.telegram_id}>
                  <td><code>{adm.telegram_id}</code></td>
                  <td><span className="role-tag">{adm.role}</span></td>
                  <td>{adm.is_active ? 'Active' : 'Inactive'}</td>
                  <td>{adm.added_by ? `ID #${adm.added_by}` : 'Bootstrap'}</td>
                  <td>{adm.created_at ? new Date(adm.created_at).toLocaleDateString() : '—'}</td>
                  <td>
                    <button className="delete-btn" type="button" onClick={() => handleDeleteAdmin(adm.telegram_id)}>
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Target</th>
              <th>Reason</th>
              <th>Source</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {auditLogs.map((log) => (
              <tr key={log.id}>
                <td>#{log.id}</td>
                <td><code>{log.actor_telegram_id}</code></td>
                <td><strong>{log.action}</strong></td>
                <td>{log.target_type} #{log.target_id}</td>
                <td>{log.reason || '—'}</td>
                <td><small>{log.source}</small></td>
                <td><small>{new Date(log.created_at).toLocaleString()}</small></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
