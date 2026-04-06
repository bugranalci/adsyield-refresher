import React, { useState } from 'react';
import { login } from '../api';

function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Email ve sifre gerekli');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await login(email, password);
      if (res.error) {
        setError(res.error);
      } else if (res.token) {
        onLogin(res.email);
      }
    } catch (err) {
      setError('Baglanti hatasi');
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <form className="login-box" onSubmit={handleSubmit}>
        <div className="login-header">
          <span className="logo">ADSYIELD</span>
          <span className="logo-sub">Refresh Tool</span>
        </div>
        {error && <div className="form-error">{error}</div>}
        <div className="form-group">
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="email@adsyield.com"
            autoFocus
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="********"
          />
        </div>
        <button className="btn btn-primary login-btn" type="submit" disabled={loading}>
          {loading ? 'Giris yapiliyor...' : 'Giris Yap'}
        </button>
      </form>
    </div>
  );
}

export default Login;
