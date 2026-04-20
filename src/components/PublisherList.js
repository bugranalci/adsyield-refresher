import React, { useState, useEffect, useCallback } from 'react';
import { getPublishers, deletePublisher } from '../api';

function PublisherList({ onAddClick, onEditClick, onSelectPublisher, refreshKey }) {
  const [publishers, setPublishers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPublishers = useCallback(() => {
    getPublishers()
      .then(data => { setPublishers(data); setLoading(false); })
      .catch(() => { setLoading(false); });
  }, []);

  useEffect(() => { fetchPublishers(); }, [fetchPublishers, refreshKey]);

  const handleDelete = async (p) => {
    if (window.confirm(`${p.name} silinsin mi? Tum app'leri ve loglari da silinecek.`)) {
      try {
        await deletePublisher(p.id);
        setPublishers(publishers.filter(pub => pub.id !== p.id));
      } catch (e) {
        alert(`Silme hatasi: ${e.message}`);
      }
    }
  };

  if (loading) return <div className="empty-state">Loading...</div>;

  return (
    <div className="publisher-list">
      <div className="section-header">
        <h2 className="section-title">Publishers</h2>
        <button className="btn btn-primary" onClick={onAddClick}>+ Add Publisher</button>
      </div>
      {publishers.length === 0 ? (
        <div className="empty-state">No publishers yet. Add one to get started.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>GAM ID</th>
              <th>Mode</th>
              <th>Frequency</th>
              <th>Last Run</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {publishers.map(p => (
              <tr key={p.id}>
                <td className="name-cell clickable" onClick={() => onSelectPublisher(p)}>
                  {p.name}
                </td>
                <td><code>{p.gam_publisher_id}</code></td>
                <td>
                  <span className={`badge ${p.mode === 'hybrid' ? 'badge-dry' : 'badge-inactive'}`}>
                    {p.mode.toUpperCase()}
                  </span>
                </td>
                <td>{p.mode === 'hybrid' ? `${p.frequency_days}d` : '—'}</td>
                <td className="date-cell">
                  {p.last_run ? new Date(p.last_run).toLocaleString() : '—'}
                </td>
                <td>
                  <span className={`badge ${p.active ? 'badge-active' : 'badge-inactive'}`}>
                    {p.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="actions">
                  <button className="btn btn-primary" onClick={() => onSelectPublisher(p)}>
                    Apps
                  </button>
                  <button className="btn btn-edit" onClick={() => onEditClick(p)}>
                    Edit
                  </button>
                  <button className="btn btn-delete" onClick={() => handleDelete(p)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default PublisherList;
