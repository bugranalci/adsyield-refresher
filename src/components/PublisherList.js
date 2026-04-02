import React, { useState, useEffect } from 'react';
import { getPublishers, runPublisher, deletePublisher } from '../api';

function PublisherList({ onAddClick, onEditClick }) {
  const [publishers, setPublishers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState(null);

  useEffect(() => {
    getPublishers().then(data => {
      setPublishers(data);
      setLoading(false);
    });
  }, []);

  const handleRun = async (id, dryRun) => {
    setRunningId(id);
    try {
      const result = await runPublisher(id, dryRun);
      if (result.status === 'no_match') {
        alert(`⚠️ ${result.message}`);
      } else if (result.status === 'done') {
        const mode = dryRun ? 'DRY-RUN' : 'CANLI';
        alert(`✅ ${mode} tamamlandı\n\nBaşarılı: ${result.success}\nHatalı: ${result.failed}\nAtlanan: ${result.skipped}`);
      } else {
        alert('Bir hata oluştu.');
      }
    } catch (e) {
      alert('Bağlantı hatası.');
    }
    setRunningId(null);
  };

  const handleDelete = async (p) => {
    if (window.confirm(`${p.name} silinsin mi?`)) {
      await deletePublisher(p.id);
      setPublishers(publishers.filter(pub => pub.id !== p.id));
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
              <th>Tag</th>
              <th>Find</th>
              <th>Replace</th>
              <th>Frequency</th>
              <th>Last Run</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {publishers.map(p => (
              <tr key={p.id}>
                <td className="name-cell">{p.name}</td>
                <td><code>{p.publisher_tag}</code></td>
                <td><code className="find">{p.find_string}</code></td>
                <td><code className="replace">{p.replace_string}</code></td>
                <td>{p.frequency_days}d</td>
                <td className="date-cell">
                  {p.last_run ? new Date(p.last_run).toLocaleString() : '—'}
                </td>
                <td>
                  <span className={`badge ${p.active ? 'badge-active' : 'badge-inactive'}`}>
                    {p.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="actions">
                  <button
                    className="btn btn-run"
                    disabled={runningId === p.id}
                    onClick={() => handleRun(p.id, false)}
                  >
                    {runningId === p.id ? '...' : '▶ Run'}
                  </button>
                  <button
                    className="btn btn-edit"
                    onClick={() => onEditClick(p)}
                  >
                    Edit
                  </button>
                  <button
                    className="btn"
                    onClick={() => handleRun(p.id, true)}
                  >
                    Dry Run
                  </button>
                  <button
                    className="btn btn-delete"
                    onClick={() => handleDelete(p)}
                  >
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