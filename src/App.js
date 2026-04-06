import React, { useState, useEffect } from 'react';
import PublisherList from './components/PublisherList';
import LogViewer from './components/LogViewer';
import PublisherForm from './components/PublisherForm';
import ApprovalList from './components/ApprovalList';
import Login from './components/Login';
import { getToken, getUserEmail, logout } from './api';
import './App.css';

function App() {
  const [loggedIn, setLoggedIn] = useState(!!getToken());
  const [userEmail, setUserEmail] = useState(getUserEmail() || '');
  const [activeTab, setActiveTab] = useState('publishers');
  const [showForm, setShowForm] = useState(false);
  const [editingPublisher, setEditingPublisher] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'approvals') {
      setActiveTab('approvals');
    }
  }, []);

  const handleSaved = () => {
    setShowForm(false);
    setEditingPublisher(null);
    setRefreshKey(k => k + 1);
  };

  if (!loggedIn) {
    return <Login onLogin={(email) => { setLoggedIn(true); setUserEmail(email); }} />;
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="logo">ADSYIELD</span>
          <span className="logo-sub">Refresh Tool</span>
        </div>
        <div className="header-right">
          <nav className="nav">
            <button
              className={`nav-btn ${activeTab === 'publishers' ? 'active' : ''}`}
              onClick={() => setActiveTab('publishers')}
            >
              Publishers
            </button>
            <button
              className={`nav-btn ${activeTab === 'approvals' ? 'active' : ''}`}
              onClick={() => setActiveTab('approvals')}
            >
              Approvals
            </button>
            <button
              className={`nav-btn ${activeTab === 'logs' ? 'active' : ''}`}
              onClick={() => setActiveTab('logs')}
            >
              Job Logs
            </button>
          </nav>
          <span className="user-email">{userEmail}</span>
          <button className="btn" onClick={logout} title="Cikis Yap">Cikis</button>
          <button
            className="theme-toggle"
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          >
            {theme === 'dark' ? '\u2600' : '\u263E'}
          </button>
        </div>
      </header>
      <main className="main">
        {activeTab === 'publishers' && (
          <PublisherList
            refreshKey={refreshKey}
            onAddClick={() => { setEditingPublisher(null); setShowForm(true); }}
            onEditClick={(p) => { setEditingPublisher(p); setShowForm(true); }}
          />
        )}
        {activeTab === 'approvals' && <ApprovalList />}
        {activeTab === 'logs' && <LogViewer />}
      </main>
      {showForm && (
        <PublisherForm
          publisher={editingPublisher}
          onClose={() => { setShowForm(false); setEditingPublisher(null); }}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

export default App;
