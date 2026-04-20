import React, { useState } from 'react';
import { createPublisher, updatePublisher } from '../api';

function PublisherForm({ onClose, onSaved, publisher }) {
  const isEdit = !!publisher;
  const [form, setForm] = useState({
    name: publisher?.name || '',
    management_key: publisher?.management_key || '',
    gam_publisher_id: publisher?.gam_publisher_id || '',
    frequency_days: publisher?.frequency_days || 2,
    active: publisher?.active ?? 1,
    mode: publisher?.mode || 'manual',
    notify_email: publisher?.notify_email || ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async () => {
    if (!isEdit) {
      if (!form.name || !form.management_key || !form.gam_publisher_id) {
        setError('Name, Management Key ve GAM Publisher ID zorunlu.');
        return;
      }
    }
    if (form.mode === 'hybrid' && !form.notify_email) {
      setError('Hybrid modda notify email zorunlu.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      if (isEdit) {
        const res = await updatePublisher(publisher.id, {
          active: parseInt(form.active),
          frequency_days: parseInt(form.frequency_days),
          mode: form.mode,
          notify_email: form.notify_email,
          gam_publisher_id: form.gam_publisher_id,
        });
        if (res.error) { setError(res.error); setLoading(false); return; }
      } else {
        await createPublisher({
          ...form,
          frequency_days: parseInt(form.frequency_days),
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
          <h3>{isEdit ? 'Edit Publisher' : 'Add Publisher'}</h3>
          <button className="modal-close" onClick={onClose}>&#x2715;</button>
        </div>
        <div className="modal-body">
          {error && <div className="form-error">{error}</div>}
          <div className="form-group">
            <label>Publisher Name</label>
            <input name="name" value={form.name} onChange={handleChange} placeholder="Mackolik" disabled={isEdit} />
          </div>
          <div className="form-group">
            <label>Management Key (AppLovin MAX)</label>
            <input name="management_key" value={form.management_key} onChange={handleChange} placeholder="MAX API key..." disabled={isEdit} />
          </div>
          <div className="form-group">
            <label>GAM Publisher ID</label>
            <input name="gam_publisher_id" value={form.gam_publisher_id} onChange={handleChange} placeholder="22860626436" />
          </div>
          <div className="form-group">
            <label>Mode</label>
            <select name="mode" value={form.mode} onChange={handleChange} className="form-select">
              <option value="manual">Manual</option>
              <option value="hybrid">Hybrid (Otomatik Dry Run + Email Onay)</option>
            </select>
          </div>
          {form.mode === 'hybrid' && (
            <>
              <div className="form-group">
                <label>Notify Email (Account Manager)</label>
                <input name="notify_email" value={form.notify_email} onChange={handleChange} placeholder="am@adsyield.com" />
              </div>
              <div className="form-group">
                <label>Frequency (days)</label>
                <input name="frequency_days" type="number" value={form.frequency_days} onChange={handleChange} />
              </div>
            </>
          )}
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
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Save Publisher'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PublisherForm;
