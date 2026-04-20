import React, { useState, useEffect, useCallback } from 'react';
import { getLogs, getSnapshots, rollbackSnapshot } from '../api';

function LogViewer() {
  const [logs, setLogs] = useState([]);
  const [snapshots, setSnapshots] = useState({});  // keyed by (max_ad_unit_id + old_value)
  const [loading, setLoading] = useState(true);
  const [rollingBackId, setRollingBackId] = useState(null);

  const fetchAll = useCallback(() => {
    setLoading(true);
    Promise.all([getLogs({limit: 200}), getSnapshots({status: 'active'})])
      .then(([logsData, snapsData]) => {
        setLogs(logsData);
        const snapMap = {};
        snapsData.forEach(s => {
          const key = `${s.max_ad_unit_id}|${s.network_ad_unit_id_old}`;
          snapMap[key] = s;
        });
        setSnapshots(snapMap);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const findSnapshot = (log) => {
    if (log.status !== 'SUCCESS') return null;
    const key = `${log.ad_unit_id}|${log.old_value}`;
    return snapshots[key];
  };

  const handleRollback = async (log) => {
    const snap = findSnapshot(log);
    if (!snap) {
      alert('Bu log icin aktif snapshot bulunamadi.');
      return;
    }
    if (!window.confirm(`Bu ad unit'i eski haline dondurmek istiyor musun?\n\n${log.new_value}\n->\n${log.old_value}`)) {
      return;
    }

    setRollingBackId(log.id);
    try {
      const res = await rollbackSnapshot(snap.id);
      if (res.error) {
        alert(`Rollback basarisiz: ${res.error}`);
      } else {
        alert('Rollback basarili');
        fetchAll();
      }
    } catch (e) {
      alert(`Hata: ${e.message}`);
    }
    setRollingBackId(null);
  };

  if (loading) return <div className="empty-state">Loading...</div>;

  return (
    <div className="log-viewer">
      <div className="section-header">
        <h2 className="section-title">Job Logs</h2>
        <button className="btn" onClick={fetchAll}>Yenile</button>
      </div>
      {logs.length === 0 ? (
        <div className="empty-state">No logs yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Publisher</th>
              <th>App</th>
              <th>Ad Unit</th>
              <th>Old</th>
              <th>New</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {logs.map(log => {
              const snap = findSnapshot(log);
              const canRollback = snap !== null && snap !== undefined;
              return (
                <tr key={log.id}>
                  <td className="date-cell">{new Date(log.ran_at).toLocaleString()}</td>
                  <td>{log.publisher_name || '—'}</td>
                  <td>{log.app_label || '—'}</td>
                  <td>{log.ad_unit_name || '—'}</td>
                  <td><code className="find">{log.old_value}</code></td>
                  <td><code className="replace">{log.new_value}</code></td>
                  <td>
                    <span className={`badge ${
                      log.status === 'SUCCESS' ? 'badge-active' :
                      log.status === 'DRY_RUN' ? 'badge-dry' :
                      log.status === 'ROLLED_BACK' ? 'badge-inactive' :
                      'badge-inactive'
                    }`}>
                      {log.status}
                    </span>
                  </td>
                  <td>
                    {canRollback && (
                      <button
                        className="btn btn-delete"
                        disabled={rollingBackId === log.id}
                        onClick={() => handleRollback(log)}
                      >
                        {rollingBackId === log.id ? '...' : 'Rollback'}
                      </button>
                    )}
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

export default LogViewer;
