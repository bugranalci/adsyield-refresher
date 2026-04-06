import React, { useState, useEffect, useCallback } from 'react';
import { getPublishers, runPublisher, deletePublisher, pollJob } from '../api';

function PublisherList({ onAddClick, onEditClick, refreshKey }) {
  const [publishers, setPublishers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState(null);
  const [runStatus, setRunStatus] = useState('');

  const fetchPublishers = useCallback(() => {
    getPublishers()
      .then(data => { setPublishers(data); setLoading(false); })
      .catch(() => { setLoading(false); });
  }, []);

  useEffect(() => { fetchPublishers(); }, [fetchPublishers, refreshKey]);

  const handleRun = async (id, dryRun) => {
    setRunningId(id);
    setRunStatus('Baslaniyor...');
    try {
      const res = await runPublisher(id, dryRun);

      if (res.error) {
        alert(res.error);
        setRunningId(null);
        setRunStatus('');
        return;
      }

      if (res.status === 'started' && res.job_id) {
        setRunStatus('Calisiyor...');
        const result = await pollJob(res.job_id, (job) => {
          if (job.status === 'running') {
            setRunStatus('Ad unit\'ler taraniyor...');
          }
        });

        if (result.status === 'no_match') {
          alert(`Eslesme bulunamadi.\n${result.message || ''}`);
        } else if (result.status === 'done') {
          const mode = dryRun ? 'DRY-RUN' : 'CANLI';
          alert(`${mode} tamamlandi\n\nBasarili: ${result.success}\nHatali: ${result.failed}\nAtlanan: ${result.skipped}`);
        } else if (result.status === 'error') {
          alert(`Hata: ${result.message}`);
        }

        fetchPublishers();
      }
    } catch (e) {
      alert(`Baglanti hatasi: ${e.message}`);
    }
    setRunningId(null);
    setRunStatus('');
  };

  const handleDelete = async (p) => {
    if (window.confirm(`${p.name} silinsin mi?`)) {
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
            {publishers.map(p => {
              const isRunning = runningId === p.id;
              const isAnyRunning = runningId !== null;
              return (
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
                      disabled={isAnyRunning}
                      onClick={() => handleRun(p.id, false)}
                    >
                      {isRunning ? runStatus : 'Run'}
                    </button>
                    <button
                      className="btn"
                      disabled={isAnyRunning}
                      onClick={() => handleRun(p.id, true)}
                    >
                      Dry Run
                    </button>
                    <button
                      className="btn btn-edit"
                      disabled={isAnyRunning}
                      onClick={() => onEditClick(p)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-delete"
                      disabled={isAnyRunning}
                      onClick={() => handleDelete(p)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default PublisherList;
