import React, { useState } from 'react';
import { Download, FileSpreadsheet, ShieldCheck, Loader2 } from 'lucide-react';
import { getExportUrl, getAuthHeaders } from '../services/api';

export default function ExportCenter() {
  const [downloading, setDownloading] = useState(null);

  const handleDownload = async (type) => {
    setDownloading(type);
    try {
      const url = getExportUrl(type);
      const headers = getAuthHeaders();
      const response = await fetch(url, { headers });
      if (!response.ok) {
        throw new Error(`Export failed with HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${type}_export.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      alert(`Could not download CSV: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="export-center-view">
      <div className="export-intro">
        <p className="eyebrow">DATA EXPORT PARITY</p>
        <h2>Download Production Records</h2>
        <p className="heading-copy">
          Generates UTF-8-SIG encoded CSV data matching the Telegram bot <code>/export</code> command byte-for-byte.
        </p>
      </div>

      <div className="export-cards-grid">
        <div className="export-card">
          <div className="card-topline">
            <span className="export-icon"><FileSpreadsheet size={24} /></span>
            <span className="parity-badge"><ShieldCheck size={14} /> Bot Parity Verified</span>
          </div>
          <h3>Tutors Dataset</h3>
          <p>Full tutor candidate database including qualifications, contact info, subcities, and status.</p>
          <button
            className="btn-primary"
            type="button"
            onClick={() => handleDownload('tutors')}
            disabled={downloading === 'tutors'}
          >
            {downloading === 'tutors' ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
            <span>Export Tutors CSV</span>
          </button>
        </div>

        <div className="export-card">
          <div className="card-topline">
            <span className="export-icon export-icon-coral"><FileSpreadsheet size={24} /></span>
            <span className="parity-badge"><ShieldCheck size={14} /> Bot Parity Verified</span>
          </div>
          <h3>Parent Requests Dataset</h3>
          <p>Full list of tutoring requests with student levels, subjects, schedule requirements, and match status.</p>
          <button
            className="btn-primary btn-coral"
            type="button"
            onClick={() => handleDownload('parents')}
            disabled={downloading === 'parents'}
          >
            {downloading === 'parents' ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
            <span>Export Parent Requests CSV</span>
          </button>
        </div>

        <div className="export-card">
          <div className="card-topline">
            <span className="export-icon"><FileSpreadsheet size={24} /></span>
            <span className="parity-badge"><ShieldCheck size={14} /> Bot Parity Verified</span>
          </div>
          <h3>Assignments Pipeline Dataset</h3>
          <p>Complete historical log of tutor-parent pairings, matching turnaround dates, and assignment statuses.</p>
          <button
            className="btn-primary"
            type="button"
            onClick={() => handleDownload('assignments')}
            disabled={downloading === 'assignments'}
          >
            {downloading === 'assignments' ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
            <span>Export Assignments CSV</span>
          </button>
        </div>
      </div>
    </div>
  );
}
