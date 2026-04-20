import React, { useState, useEffect, useCallback } from 'react';
import { getSlotStatus, runApp, pollJob } from '../api';

function AppDetail({ app, onBack }) {
  const [slotData, setSlotData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState('');

  const fetchSlots = useCallback(() => {
    setLoading(true);
    getSlotStatus(app.id)
      .then(data => { setSlotData(data); setLoading(false); })
      .catch(e => { setLoading(false); alert(e.message); });
  }, [app.id]);

  useEffect(() => { fetchSlots(); }, [fetchSlots]);

  const handleRun = async (dryRun) => {
    if (!dryRun) {
      if (!window.confirm(`${app.label} icin CANLI RUN baslatilacak. Emin misiniz?`)) return;
    }

    setRunning(true);
    setRunStatus(dryRun ? 'Dry run baslatiliyor...' : 'Canli run baslatiliyor...');

    try {
      const res = await runApp(app.id, dryRun);
      if (res.error) {
        alert(res.error);
        setRunning(false);
        setRunStatus('');
        return;
      }

      if (res.status === 'started' && res.job_id) {
        setRunStatus(dryRun ? 'GAM ve MAX taraniyor...' : 'Guncellemeler uygulaniyor...');

        const result = await pollJob(res.job_id);

        if (result.status === 'no_match') {
          setRunStatus('Guncelleme gereken slot yok.');
          alert('Tum slot\'lar zaten guncel.');
        } else if (result.status === 'done') {
          const mode = dryRun ? 'DRY-RUN' : 'CANLI';
          setRunStatus(`${mode} tamamlandi.`);
          alert(`${mode} tamamlandi\n\nBasarili: ${result.success}\nHatali: ${result.failed}\nAtlanan: ${result.skipped}`);
        } else if (result.status === 'gam_error') {
          setRunStatus('GAM hatasi');
          alert(`GAM hatasi: ${result.error}`);
        } else if (result.status === 'error') {
          setRunStatus('Hata');
          alert(`Hata: ${result.message}`);
        }

        fetchSlots();
      }
    } catch (e) {
      alert(`Baglanti hatasi: ${e.message}`);
    }
    setRunning(false);
  };

  if (loading) return <div className="empty-state">Loading...</div>;
  if (!slotData) return <div className="empty-state">App yuklenemedi.</div>;

  const { slots } = slotData;

  return (
    <div className="app-detail">
      <div className="section-header">
        <div>
          <button className="btn" onClick={onBack}>&larr; Apps</button>
          <h2 className="section-title" style={{marginTop: 12}}>{app.label}</h2>
          <div className="date-cell" style={{marginTop: 4}}>
            GAM: {app.gam_app_name} &middot; Platform: {app.platform.toUpperCase()}
          </div>
        </div>
        <div style={{display: 'flex', gap: 8}}>
          <button className="btn" disabled={running} onClick={() => handleRun(true)}>
            {running && runStatus ? runStatus : 'Dry Run'}
          </button>
          <button className="btn btn-run" disabled={running} onClick={() => handleRun(false)}>
            Run
          </button>
        </div>
      </div>

      <h3 className="section-title" style={{fontSize: 14, marginTop: 32, marginBottom: 16}}>
        Slot Status (GAM cache)
      </h3>

      {slots.length === 0 ? (
        <div className="empty-state">
          Henuz slot cache yok. Bir Dry Run calistir, sistem GAM'den slot'lari cekecek.
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Format</th>
              <th>Platform</th>
              <th>CPM</th>
              <th>GAM Max Version</th>
              <th>Last Sync</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((s, i) => (
              <tr key={i}>
                <td><code>{s.format}</code></td>
                <td>{s.platform.toUpperCase()}</td>
                <td>${typeof s.cpm === 'number' ? s.cpm.toFixed(2) : s.cpm}</td>
                <td style={{color: '#00ff88', fontWeight: 'bold'}}>V{s.max_version}</td>
                <td className="date-cell">{new Date(s.synced_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default AppDetail;
