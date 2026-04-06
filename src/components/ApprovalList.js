import React, { useState, useEffect } from 'react';
import { getApprovals, getApprovalDetail, confirmApproval, pollJob } from '../api';

function ApprovalList() {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmStatus, setConfirmStatus] = useState('');

  const fetchApprovals = () => {
    getApprovals()
      .then(data => { setApprovals(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchApprovals(); }, []);

  // URL'den job_id varsa otomatik detay aç
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get('job_id');
    if (jobId) {
      getApprovalDetail(jobId).then(d => {
        if (!d.error) setDetail(d);
      }).catch(() => {});
    }
  }, []);

  const handleViewDetail = async (jobId) => {
    try {
      const d = await getApprovalDetail(jobId);
      if (d.error) { alert(d.error); return; }
      setDetail(d);
    } catch (e) {
      alert(e.message);
    }
  };

  const handleConfirm = async () => {
    if (!detail) return;
    if (!window.confirm(`${detail.publisher_name} icin CANLI RUN baslatilacak. Emin misiniz?`)) return;

    setConfirming(true);
    setConfirmStatus('Onaylaniyor...');
    try {
      const res = await confirmApproval(detail.job_id);
      if (res.error) {
        alert(res.error);
        setConfirming(false);
        setConfirmStatus('');
        return;
      }

      setConfirmStatus('Canli run calisiyor...');

      if (res.run_job_id) {
        const result = await pollJob(res.run_job_id);
        if (result.status === 'done') {
          setConfirmStatus(`Tamamlandi! Basarili: ${result.success}, Hatali: ${result.failed}`);
        } else if (result.status === 'error') {
          setConfirmStatus(`Hata: ${result.message}`);
        } else {
          setConfirmStatus(`Sonuc: ${result.status}`);
        }
      }

      fetchApprovals();
    } catch (e) {
      setConfirmStatus(`Hata: ${e.message}`);
    }
    setConfirming(false);
  };

  if (loading) return <div className="empty-state">Loading...</div>;

  // Detay görünümü
  if (detail) {
    return (
      <div className="approval-detail">
        <div className="section-header">
          <h2 className="section-title">Onay Detayi</h2>
          <button className="btn" onClick={() => { setDetail(null); setConfirmStatus(''); }}>Geri</button>
        </div>

        <div className="approval-info">
          <table className="table">
            <tbody>
              <tr><td className="date-cell">Publisher</td><td className="name-cell">{detail.publisher_name}</td></tr>
              <tr><td className="date-cell">Find</td><td><code className="find">{detail.find_string}</code></td></tr>
              <tr><td className="date-cell">Replace</td><td><code className="replace">{detail.replace_string}</code></td></tr>
              <tr><td className="date-cell">Eslesme</td><td style={{color:'#00ff88', fontWeight:'bold'}}>{detail.matched}</td></tr>
              <tr><td className="date-cell">Atlanan</td><td>{detail.skipped}</td></tr>
              <tr><td className="date-cell">Durum</td><td>
                <span className={`badge ${detail.status === 'pending' ? 'badge-dry' : detail.status === 'approved' ? 'badge-active' : 'badge-inactive'}`}>
                  {detail.status.toUpperCase()}
                </span>
              </td></tr>
              <tr><td className="date-cell">Olusturulma</td><td className="date-cell">{new Date(detail.created_at).toLocaleString()}</td></tr>
              <tr><td className="date-cell">Son gecerlilik</td><td className="date-cell">{new Date(detail.expires_at).toLocaleString()}</td></tr>
            </tbody>
          </table>
        </div>

        {detail.logs && detail.logs.length > 0 && (
          <>
            <h3 className="section-title" style={{marginTop: 24, marginBottom: 16}}>DRY RUN SONUCLARI</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Ad Unit</th>
                  <th>Eski ID</th>
                  <th>Yeni ID</th>
                </tr>
              </thead>
              <tbody>
                {detail.logs.map((log, i) => (
                  <tr key={i}>
                    <td>{log.ad_unit_name}</td>
                    <td><code className="find">{log.old_value}</code></td>
                    <td><code className="replace">{log.new_value}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {detail.status === 'pending' && (
          <div style={{marginTop: 24, display: 'flex', gap: 12, alignItems: 'center'}}>
            <button
              className="btn btn-run"
              onClick={handleConfirm}
              disabled={confirming}
              style={{padding: '10px 24px', fontSize: 14}}
            >
              {confirming ? confirmStatus : 'Confirm Run — Canli Calistir'}
            </button>
            {confirmStatus && !confirming && (
              <span style={{color: '#00ff88', fontSize: 13}}>{confirmStatus}</span>
            )}
          </div>
        )}
      </div>
    );
  }

  // Liste görünümü
  return (
    <div className="approval-list">
      <div className="section-header">
        <h2 className="section-title">Bekleyen Onaylar</h2>
        <button className="btn" onClick={fetchApprovals}>Yenile</button>
      </div>
      {approvals.length === 0 ? (
        <div className="empty-state">Bekleyen onay yok.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Publisher</th>
              <th>Find → Replace</th>
              <th>Eslesme</th>
              <th>Durum</th>
              <th>Islem</th>
            </tr>
          </thead>
          <tbody>
            {approvals.map(a => (
              <tr key={a.job_id}>
                <td className="date-cell">{new Date(a.created_at).toLocaleString()}</td>
                <td className="name-cell">{a.publisher_name}</td>
                <td>
                  <code className="find">{a.find_string}</code>
                  <span style={{color:'#555', margin:'0 6px'}}>→</span>
                  <code className="replace">{a.replace_string}</code>
                </td>
                <td style={{color:'#00ff88', fontWeight:'bold'}}>{a.matched}</td>
                <td>
                  <span className="badge badge-dry">PENDING</span>
                </td>
                <td>
                  <button className="btn btn-primary" onClick={() => handleViewDetail(a.job_id)}>
                    Detay ve Onayla
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

export default ApprovalList;
