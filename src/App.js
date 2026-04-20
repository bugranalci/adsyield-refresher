import React, { useState, useEffect } from 'react';
import PublisherList from './components/PublisherList';
import PublisherForm from './components/PublisherForm';
import AppList from './components/AppList';
import AppDetail from './components/AppDetail';
import LogViewer from './components/LogViewer';
import ApprovalList from './components/ApprovalList';
import Login from './components/Login';
import { getToken, getUserEmail, logout } from './api';
import './App.css';

function App() {
  const [loggedIn, setLoggedIn] = useState(!!getToken());
  const [userEmail, setUserEmail] = useState(getUserEmail() || '');
  const [activeTab, setActiveTab] = useState('publishers');

  // Drill-down state
  const [selectedPublisher, setSelectedPublisher] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);

  // Modal state
  const [showPubForm, setShowPubForm] = useState(false);
  const [editingPublisher, setEditingPublisher] = useState(null);

  const [refreshKey, setRefreshKey] = useState(0);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'approvals') setActiveTab('approvals');
  }, []);

  const handlePubSaved = () => {
    setShowPubForm(false);
    setEditingPublisher(null);
    setRefreshKey(k => k + 1);
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSelectedPublisher(null);
    setSelectedApp(null);
  };

  if (!loggedIn) {
    return <Login onLogin={(email) => { setLoggedIn(true); setUserEmail(email); }} />;
  }

  const renderMain = () => {
    if (activeTab === 'publishers') {
      if (selectedApp) {
        return <AppDetail
          app={selectedApp}
          onBack={() => setSelectedApp(null)}
        />;
      }
      if (selectedPublisher) {
        return <AppList
          publisher={selectedPublisher}
          onBack={() => setSelectedPublisher(null)}
          onSelectApp={setSelectedApp}
        />;
      }
      return <PublisherList
        refreshKey={refreshKey}
        onAddClick={() => { setEditingPublisher(null); setShowPubForm(true); }}
        onEditClick={(p) => { setEditingPublisher(p); setShowPubForm(true); }}
        onSelectPublisher={setSelectedPublisher}
      />;
    }
    if (activeTab === 'approvals') return <ApprovalList />;
    if (activeTab === 'logs') return <LogViewer />;
    return null;
  };

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
              onClick={() => handleTabChange('publishers')}
            >
              Publishers
            </button>
            <button
              className={`nav-btn ${activeTab === 'approvals' ? 'active' : ''}`}
              onClick={() => handleTabChange('approvals')}
            >
              Approvals
            </button>
            <button
              className={`nav-btn ${activeTab === 'logs' ? 'active' : ''}`}
              onClick={() => handleTabChange('logs')}
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
        {renderMain()}
      </main>
      {showPubForm && (
        <PublisherForm
          publisher={editingPublisher}
          onClose={() => { setShowPubForm(false); setEditingPublisher(null); }}
          onSaved={handlePubSaved}
        />
      )}
    </div>
  );
}

export default App;
