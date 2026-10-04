import React, { useEffect, useState } from 'react';
import { UserPlus, Trash2, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { getAdminUsers, createAdminUser, deleteAdminUser, getAdminAuditLog } from '../services/api';

const AUDIT_PAGE_SIZE = 20;

export default function AdminManagement() {
  const [admins, setAdmins] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [activeTab, setActiveTab] = useState('admins');
  const [newTelegramId, setNewTelegramId] = useState('');
  const [newRole, setNewRole] = useState('admin');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [saving, setSaving] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  const loadData = async (page = auditPage) => {
    setLoading(true);
    setError(null);
    try {
      const [adminsData, auditData] = await Promise.all([
        getAdminUsers(),
        getAdminAuditLog({ page, page_size: AUDIT_PAGE_SIZE }),
      ]);
      setAdmins(adminsData.items || []);
      setAuditLogs(auditData.items || []);
      setAuditTotal(auditData.total || 0);
    } catch (err) {
      setError(err.message || 'Failed to load admin management.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(1);
  }, []);

  useEffect(() => {
    if (activeTab === 'audit') loadData(auditPage);
  }, [auditPage]);

  const auditTotalPages = Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE));

  const handleAddAdmin = async (e) => {
    e.preventDefault();
    setFeedback(null);
    const rawId = newTelegramId.trim();
    if (!/^\d+$/.test(rawId)) {
      setFeedback({ type: 'error', message: 'Enter a valid numeric Telegram ID.' });
      return;
    }
    const telegramId = Number(rawId);
    if (!Number.isSafeInteger(telegramId) || telegramId <= 0) {
      setFeedback({ type: 'error', message: 'Telegram ID is outside the supported range.' });
      return;
    }

    setSaving(true);
    try {
      await createAdminUser({ telegram_id: telegramId, role: newRole });
      setNewTelegramId('');
      setFeedback({ type: 'success', message: `${newRole === 'super_admin' ? 'Super Admin' : 'Admin'} ${telegramId} was added successfully.` });
      await loadData();
    } catch (err) {
      const message = err.status === 409
        ? 'That Telegram ID is already an admin.'
        : err.status === 403
          ? 'You do not have permission to manage admins.'
          : `Could not add admin: ${err.message}`;
      setFeedback({ type: 'error', message });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAdmin = async (telegramId) => {
    const confirmed = window.confirm(`Remove admin ${telegramId}? This cannot be undone from this screen.`);
    if (!confirmed) return;

    setRemovingId(telegramId);
    setFeedback(null);
    try {
      await deleteAdminUser(telegramId);
      setFeedback({ type: 'success', message: `Admin ${telegramId} was removed.` });
      await loadData();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.status === 409
          ? 'You cannot remove your own admin account.'
          : `Could not remove admin: ${err.message}`,
      });
    } finally {
      setRemovingId(null);
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
            Audit Trail ({auditTotal})
          </button>
        </div>
      </div>

      {feedback && (
        <div className={feedback.type === 'success' ? 'form-feedback form-feedback-success' : 'form-feedback form-feedback-error'} role={feedback.type === 'success' ? 'status' : 'alert'}>
          {feedback.message}
        </div>
      )}

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
              <option value="admin">Admin</option>
              <option value="super_admin">Super Admin</option>
            </select>
            <button className="btn-primary" type="submit" disabled={saving}>
              {saving ? <Loader2 className="spin" size={16} /> : <UserPlus size={16} />}
              <span>{saving ? 'Adding…' : 'Add Admin'}</span>
            </button>
          </form>

          <div className="table-scroll">
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
                    <button className="delete-btn" type="button" disabled={removingId === adm.telegram_id} onClick={() => handleDeleteAdmin(adm.telegram_id)} aria-label={`Remove admin ${adm.telegram_id}`}>
                      {removingId === adm.telegram_id ? <Loader2 className="spin" size={14} /> : <Trash2 size={14} />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      ) : (
        <>
        <div className="table-scroll">
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
        </div>
        <div className="pagination-row">
          <span>{auditTotal ? `${(auditPage - 1) * AUDIT_PAGE_SIZE + 1}–${Math.min(auditPage * AUDIT_PAGE_SIZE, auditTotal)} of ${auditTotal}` : '0 entries'}</span>
          <div>
            <button className="icon-button" type="button" aria-label="Previous page" disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}><ChevronLeft size={16} /></button>
            <span>Page {auditPage} / {auditTotalPages}</span>
            <button className="icon-button" type="button" aria-label="Next page" disabled={auditPage >= auditTotalPages} onClick={() => setAuditPage((p) => p + 1)}><ChevronRight size={16} /></button>
          </div>
        </div>
        </>
      )}
    </div>
  );
}
