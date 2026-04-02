import React, { useState } from 'react';
import PublisherList from './components/PublisherList';
import LogViewer from './components/LogViewer';
import PublisherForm from './components/PublisherForm';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('publishers');
  const [showForm, setShowForm] = useState(false);
  const [editingPublisher, setEditingPublisher] = useState(null);

  const handleSaved = () => {
    setShowForm(false);
    setEditingPublisher(null);
    window.location.reload();
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="logo">ADSYIELD</span>
          <span className="logo-sub">Refresh Tool</span>
        </div>
        <nav className="nav">
          <button
            className={`nav-btn ${activeTab === 'publishers' ? 'active' : ''}`}
            onClick={() => setActiveTab('publishers')}
          >
            Publishers
          </button>
          <button
            className={`nav-btn ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            Job Logs
          </button>
        </nav>
      </header>
      <main className="main">
        {activeTab === 'publishers' ? (
          <PublisherList
            onAddClick={() => { setEditingPublisher(null); setShowForm(true); }}
            onEditClick={(p) => { setEditingPublisher(p); setShowForm(true); }}
          />
        ) : (
          <LogViewer />
        )}
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