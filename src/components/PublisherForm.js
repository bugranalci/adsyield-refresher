import React, { useState } from 'react';
import { createPublisher, updatePublisher } from '../api';

function PublisherForm({ onClose, onSaved, publisher }) {
  const isEdit = !!publisher;
  const [form, setForm] = useState({
    name: publisher?.name || '',
    management_key: publisher?.management_key || '',
    publisher_tag: publisher?.publisher_tag || '',
    find_string: publisher?.find_string || '',
    replace_string: publisher?.replace_string || '',
    frequency_days: publisher?.frequency_days || 2,
    active: publisher?.active ?? 1
  });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async () => {
    if (!form.name || !form.management_key || !form.publisher_tag || !form.find_string || !form.replace_string) {
      alert('Tüm alanları doldur.');
      return;
    }
    setLoading(true);
    if (isEdit) {
      await updatePublisher(publisher.id, {
        find_string: form.find_string,
        replace_string: form.replace_string,
        frequency_days: parseInt(form.frequency_days),
        active: parseInt(form.active)
      });
    } else {
      await createPublisher({ ...form, frequency_days: parseInt(form.frequency_days) });
    }
    setLoading(false);
    onSaved();
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Publisher' : 'Add Publisher'}</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label>Publisher Name</label>
            <input name="name" value={form.name} onChange={handleChange} placeholder="TheGameOps" disabled={isEdit} />
          </div>
          <div className="form-group">
            <label>Management Key</label>
            <input name="management_key" value={form.management_key} onChange={handleChange} placeholder="API key..." disabled={isEdit} />
          </div>
          <div className="form-group">
            <label>Publisher Tag</label>
            <input name="publisher_tag" value={form.publisher_tag} onChange={handleChange} placeholder="thegameops" disabled={isEdit} />
          </div>
          <div className="form-group">
            <label>Find String</label>
            <input name="find_string" value={form.find_string} onChange={handleChange} placeholder="_v45_" />
          </div>
          <div className="form-group">
            <label>Replace String</label>
            <input name="replace_string" value={form.replace_string} onChange={handleChange} placeholder="_v46_" />
          </div>
          <div className="form-group">
            <label>Frequency (days)</label>
            <input name="frequency_days" type="number" value={form.frequency_days} onChange={handleChange} />
          </div>
          {isEdit && (
            <div className="form-group">
              <label>Status</label>
              <select name="active" value={form.active} onChange={handleChange} style={{background:'#0d0d0d', border:'1px solid #333', color:'#e0e0e0', padding:'10px 12px', fontFamily:'monospace'}}>
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