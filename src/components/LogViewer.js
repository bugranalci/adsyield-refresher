import React, { useState, useEffect } from 'react';
import { getLogs } from '../api';

function LogViewer() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLogs().then(data => {
      setLogs(data);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="empty-state">Loading...</div>;

  return (
    <div className="log-viewer">
      <div className="section-header">
        <h2 className="section-title">Job Logs</h2>
        <button className="btn" onClick={() => getLogs().then(setLogs)}>↻ Refresh</button>
      </div>
      {logs.length === 0 ? (
        <div className="empty-state">No logs yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Publisher</th>
              <th>Ad Unit</th>
              <th>Old ID</th>
              <th>New ID</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map(log => (
              <tr key={log.id}>
                <td className="date-cell">{new Date(log.ran_at).toLocaleString()}</td>
                <td>{log.publisher_name}</td>
                <td>{log.ad_unit_name}</td>
                <td><code className="find">{log.old_value}</code></td>
                <td><code className="replace">{log.new_value}</code></td>
                <td>
                  <span className={`badge ${log.status === 'SUCCESS' ? 'badge-active' : log.status === 'DRY_RUN' ? 'badge-dry' : 'badge-inactive'}`}>
                    {log.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default LogViewer;