import React, { useState } from 'react';
import { createApp, updateApp } from '../api';

function AppForm({ onClose, onSaved, publisher, app }) {
  const isEdit = !!app;
  const [form, setForm] = useState({
    label: app?.label || '',
    gam_app_name: app?.gam_app_name || '',
    platform: app?.platform || 'aos',
    active: app?.active ?? 1,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async () => {
    if (!form.label || !form.gam_app_name || !form.platform) {
      setError('Tum alanlari doldur.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      if (isEdit) {
        const res = await updateApp(app.id, {
          label: form.label,
          gam_app_name: form.gam_app_name,
          platform: form.platform,
          active: parseInt(form.active),
        });
        if (res.error) { setError(res.error); setLoading(false); return; }
      } else {
        await createApp({
          publisher_id: publisher.id,
          label: form.label,
          gam_app_name: form.gam_app_name,
          platform: form.platform,
        });
      }
      onSaved();
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>{isEdit ? 'Edit App' : 'Add App'}</h3>
          <button className="modal-close" onClick={onClose}>&#x2715;</button>
        </div>
        <div className="modal-body">
          {error && <div className="form-error">{error}</div>}
          <div className="form-group">
            <label>Label (UI'da gosterilen)</label>
            <input name="label" value={form.label} onChange={handleChange} placeholder="Mackolik AOS" />
          </div>
          <div className="form-group">
            <label>GAM App Name (path'deki klasor adi, birebir)</label>
            <input name="gam_app_name" value={form.gam_app_name} onChange={handleChange} placeholder="Mackolik" />
          </div>
          <div className="form-group">
            <label>Platform</label>
            <select name="platform" value={form.platform} onChange={handleChange} className="form-select">
              <option value="aos">Android (aos)</option>
              <option value="ios">iOS (ios)</option>
            </select>
          </div>
          {isEdit && (
            <div className="form-group">
              <label>Status</label>
              <select name="active" value={form.active} onChange={handleChange} className="form-select">
                <option value={1}>Active</option>
                <option value={0}>Inactive</option>
              </select>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Save App'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AppForm;
