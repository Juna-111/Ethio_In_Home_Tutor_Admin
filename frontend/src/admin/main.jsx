import React from 'react';
import ReactDOM from 'react-dom/client';
import AdminApp from './AdminApp.jsx';
import AppErrorBoundary from '../components/AppErrorBoundary.jsx';
import './admin.css';

ReactDOM.createRoot(document.getElementById('admin-root')).render(
  <React.StrictMode>
    <AppErrorBoundary admin>
      <AdminApp />
    </AppErrorBoundary>
  </React.StrictMode>,
);