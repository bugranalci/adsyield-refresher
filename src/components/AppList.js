import React, { useState, useEffect, useCallback } from 'react';
import { getPublisherApps, deleteApp } from '../api';
import AppForm from './AppForm';

function AppList({ publisher, onBack, onSelectApp }) {
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingApp, setEditingApp] = useState(null);

  const fetchApps = useCallback(() => {
    getPublisherApps(publisher.id)
      .then(data => { setApps(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [publisher.id]);

  useEffect(() => { fetchApps(); }, [fetchApps]);

  const handleDelete = async (a) => {
    if (window.confirm(`${a.label} silinsin mi?`)) {
      try {
        await deleteApp(a.id);
        fetchApps();
      } catch (e) {
        alert(`Silme hatasi: ${e.message}`);
      }
    }
  };

  const handleSaved = () => {
    setShowForm(false);
    setEditingApp(null);
    fetchApps();
  };

  if (loading) return <div className="empty-state">Loading...</div>;

  return (
    <div className="app-list">
      <div className="section-header">
        <div>
          <button className="btn" onClick={onBack}>&larr; Publishers</button>
          <h2 className="section-title" style={{marginTop: 12}}>{publisher.name} &mdash; Apps</h2>
          <div className="date-cell" style={{marginTop: 4}}>GAM: {publisher.gam_publisher_id}</div>
        </div>
        <button className="btn btn-primary" onClick={() => { setEditingApp(null); setShowForm(true); }}>
          + Add App
        </button>
      </div>

      {apps.length === 0 ? (
        <div className="empty-state">No apps yet. Add one to get started.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Label</th>
              <th>GAM App Name</th>
              <th>Platform</th>
              <th>Last Run</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {apps.map(a => (
              <tr key={a.id}>
                <td className="name-cell clickable" onClick={() => onSelectApp(a)}>
                  {a.label}
                </td>
                <td><code>{a.gam_app_name}</code></td>
                <td>
                  <span className="badge badge-inactive">{a.platform.toUpperCase()}</span>
                </td>
                <td className="date-cell">
                  {a.last_run ? new Date(a.last_run).toLocaleString() : '—'}
                </td>
                <td>
                  <span className={`badge ${a.active ? 'badge-active' : 'badge-inactive'}`}>
                    {a.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="actions">
                  <button className="btn btn-primary" onClick={() => onSelectApp(a)}>
                    Open
                  </button>
                  <button className="btn btn-edit" onClick={() => { setEditingApp(a); setShowForm(true); }}>
                    Edit
                  </button>
                  <button className="btn btn-delete" onClick={() => handleDelete(a)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showForm && (
        <AppForm
          publisher={publisher}
          app={editingApp}
          onClose={() => { setShowForm(false); setEditingApp(null); }}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

export default AppList;
