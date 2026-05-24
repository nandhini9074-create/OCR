import React, { useState, useRef, useEffect } from 'react';
import { 
  Upload, 
  Mail, 
  FileText, 
  CheckCircle2, 
  Clock, 
  Sparkles, 
  Server, 
  ChevronRight, 
  Copy, 
  Check, 
  Search, 
  Brain, 
  AlertCircle,
  Award,
  Calendar,
  MapPin,
  X,
  ScanText,
  Download,
  FolderOpen,
  Trash2,
  RefreshCw,
  Database,
  Cpu
} from 'lucide-react';
import './App.css';

const API_BASE_URL = 'http://localhost:8001';

function App() {
  const [file, setFile] = useState(null);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [response, setResponse] = useState(null);
  const [activeTab, setActiveTab] = useState('visual');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [ocrPreview, setOcrPreview] = useState(null);
  const [ocrCopied, setOcrCopied] = useState(false);
  const [clearCacheStatus, setClearCacheStatus] = useState(null); // null | 'clearing' | 'done' | 'error'
  const fileInputRef = useRef(null);

  // Email Intelligence Hub State Variables
  const [activeView, setActiveView] = useState('certificate'); // 'certificate' | 'semantic_search'
  const [userEmail, setUserEmail] = useState('alex@example.com');
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchMode, setSearchMode] = useState('rag'); // 'rag' | 'vector'
  const [searchLimit, setSearchLimit] = useState(5);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [emailHubError, setEmailHubError] = useState(null);
  const [gdprWiping, setGdprWiping] = useState(false);

  // Fetch email inbox sync status
  const fetchSyncStatus = async (emailToFetch = userEmail) => {
    if (!emailToFetch.trim()) return;
    try {
      const res = await fetch(`${API_BASE_URL}/emails/status?user_id=${encodeURIComponent(emailToFetch.trim())}`);
      if (res.ok) {
        const data = await res.json();
        setSyncStatus(data);
        setEmailHubError(null);
      } else {
        throw new Error(`Failed to fetch sync status (${res.status})`);
      }
    } catch (err) {
      console.error("Quiet sync status fetch failed:", err);
    }
  };

  // Poll sync status when Email Hub is active
  useEffect(() => {
    if (activeView === 'semantic_search' && userEmail) {
      fetchSyncStatus();
      const interval = setInterval(() => {
        fetchSyncStatus();
      }, 5000); // Poll status logs dynamically every 5 seconds
      return () => clearInterval(interval);
    }
  }, [activeView, userEmail]);

  // Handle popup window OAuth flow authentication links
  const handleConnectOAuth = async (provider, overrideEmail = null) => {
    const targetEmail = overrideEmail || userEmail;
    if (!targetEmail.trim()) {
      setEmailHubError('Please enter a valid email address first.');
      return;
    }
    setEmailHubError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/${provider}/login?user_id=${encodeURIComponent(targetEmail.trim())}`);
      if (!res.ok) throw new Error(`OAuth login request failed for provider: ${provider}`);
      const data = await res.json();
      
      if (data.redirect_url) {
        const width = 600;
        const height = 700;
        const left = window.screen.width / 2 - width / 2;
        const top = window.screen.height / 2 - height / 2;
        
        const popup = window.open(
          data.redirect_url,
          `Connect ${provider === 'google' ? 'Gmail' : 'Outlook'}`,
          `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes,status=yes`
        );
        
        // Poll and detect popup close to auto-fetch new connections status
        const pollTimer = setInterval(() => {
          if (!popup || popup.closed) {
            clearInterval(pollTimer);
            fetchSyncStatus();
          }
        }, 1000);
      }
    } catch (err) {
      setEmailHubError(err.message || 'Failed to initiate OAuth authorization.');
    }
  };

  // Trigger mailbox incremental synchronization
  const handleTriggerSync = async (provider) => {
    if (!userEmail.trim()) {
      setEmailHubError('Please enter a valid email address first.');
      return;
    }
    setEmailHubError(null);
    setSyncLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/emails/sync?user_id=${encodeURIComponent(userEmail.trim())}&provider=${provider}`
      );
      if (!res.ok) throw new Error('Mailbox synchronization request failed.');
      
      // Instantly query status database to display progress
      await fetchSyncStatus();
    } catch (err) {
      setEmailHubError(err.message || 'Failed to initiate background sync.');
    } finally {
      setSyncLoading(false);
    }
  };

  // Perform GDPR Revocation deletion wipe
  const handleWipeData = async () => {
    if (!userEmail.trim()) return;
    if (!window.confirm('WARNING: This will permanently wipe all SQLite database metadata, OAuth records, and Qdrant vector embeddings for this email. This action cannot be undone. Are you sure?')) {
      return;
    }
    
    setGdprWiping(true);
    setEmailHubError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/emails/delete?user_id=${encodeURIComponent(userEmail.trim())}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Wipe operation failed');
      
      setSearchResults(null);
      setSyncStatus(null);
      alert('GDPR data wipe completed successfully.');
      await fetchSyncStatus();
    } catch (err) {
      setEmailHubError(err.message || 'Failed to perform GDPR deletion.');
    } finally {
      setGdprWiping(false);
    }
  };

  // Semantic Similarity Search & AI Conversational RAG
  const handleSemanticSearch = async (e) => {
    e.preventDefault();
    if (!userEmail.trim()) {
      setEmailHubError('Please enter an email address associated with your inbox.');
      return;
    }
    if (!searchQuery.trim()) return;
    
    setSearchLoading(true);
    setSearchResults(null);
    setEmailHubError(null);
    
    try {
      const endpoint = searchMode === 'rag' ? '/rag/query' : '/search';
      const body = {
        user_id: userEmail.trim(),
        query: searchQuery.trim(),
        limit: parseInt(searchLimit)
      };
      
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });
      
      if (!res.ok) {
        throw new Error(`Search request failed (${res.status})`);
      }
      
      const data = await res.json();
      setSearchResults(data);
    } catch (err) {
      setEmailHubError(err.message || 'Failed to complete semantic search.');
    } finally {
      setSearchLoading(false);
    }
  };

  // RAG summary custom formatting parser for premium styling
  const renderFormattedSummary = (summaryText) => {
    if (!summaryText) return null;
    const lines = summaryText.split('\n');
    return lines.map((line, idx) => {
      let formattedLine = line;
      
      // Format bold text (**text**)
      const boldRegex = /\*\*(.*?)\*\*/g;
      formattedLine = formattedLine.replace(boldRegex, '<strong>$1</strong>');
      
      // Format citation badge tags ([1])
      const citationRegex = /\[(\d+)\]/g;
      formattedLine = formattedLine.replace(citationRegex, '<span class="citation-badge">$1</span>');
      
      return (
        <p 
          key={idx} 
          className="rag-paragraph" 
          dangerouslySetInnerHTML={{ __html: formattedLine }}
          style={{ marginBottom: '0.8rem', lineHeight: '1.6' }}
        />
      );
    });
  };

  // Execution Steps configuration
  const steps = [
    { num: 1, name: 'Secure Ingestion & Hashing', desc: 'Secure local storage & calculate SHA-256 footprint' },
    { num: 2, name: 'OCR Text Layer Analysis', desc: 'Extract raw text layers using digital parser or PaddleOCR' },
    { num: 3, name: 'Structured Metadata Extraction', desc: 'Isolate recipient, issuer, issuing date, and skills using LLM' },
    { num: 4, name: 'Email Ingestion & Matching', desc: 'Scan mailbox headers & confirm cognitive link' },
    { num: 5, name: 'Tavily Web Search Enrichment', desc: 'Query parallel search threads for background context' },
    { num: 6, name: '3-Way Cognitive Synthesis', desc: 'Consolidate OCR + Email + Web; resolve conflicts' },
  ];

  // Animate progress indicators during network calls
  useEffect(() => {
    let interval = null;
    if (loading) {
      setCurrentStep(1);
      interval = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev < 5) return prev + 1;
          return prev;
        });
      }, 2200);
    } else {
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [loading]);

  // Clipboard paste handler
  useEffect(() => {
    const handlePasteEvent = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
          const blob = items[i].getAsFile();
          if (blob) {
            const pastedFile = new File([blob], `pasted-screenshot-${Date.now()}.png`, { type: blob.type });
            validateAndSetFile(pastedFile);
            break;
          }
        }
      }
    };

    window.addEventListener('paste', handlePasteEvent);
    return () => window.removeEventListener('paste', handlePasteEvent);
  }, []);

  // Drag and Drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    const allowedExtensions = ['png', 'jpg', 'jpeg', 'webp', 'pdf', 'txt'];
    const ext = selectedFile.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(ext)) {
      setError('Unsupported file type. Please upload PNG, JPG, JPEG, WEBP, PDF, or TXT.');
      return;
    }
    
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('File size too large. Maximum supported size is 10MB.');
      return;
    }

    setError(null);
    setFile(selectedFile);
  };

  const removeFile = () => {
    setFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Submit file and optional email filter to the backend
  const analyzeDocument = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setResponse(null);
    setError(null);
    setActiveTab('visual');
    setOcrPreview(null); // Clear previous OCR preview on new search

    // --- JUST IN TIME OAUTH FLOW ---
    if (email.trim()) {
      // 1. Open an empty popup synchronously FIRST to bypass browser popup blockers
      // We must do this before ANY 'await' calls, otherwise the browser will block it!
      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;
      let authPopup = window.open(
        'about:blank',
        `Connect Gmail`,
        `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes,status=yes`
      );

      try {
        // Forcefully fetch the secure URL from the backend every time, ignoring previous connections
        const authRes = await fetch(`${API_BASE_URL}/auth/google/login?user_id=${encodeURIComponent(email.trim())}`);
        if (authRes.ok) {
          const authData = await authRes.json();
          if (authData.redirect_url && authPopup) {
            // 3. Redirect the already-open popup to Google
            authPopup.location.href = authData.redirect_url;
            
            // Wait for the popup to close before proceeding with the analysis
            await new Promise((resolve) => {
              const pollTimer = setInterval(() => {
                if (authPopup.closed) {
                  clearInterval(pollTimer);
                  resolve();
                }
              }, 1000);
            });
            
            // Post-Popup Verification: Check if the user successfully completed the OAuth flow
            try {
              const verifyRes = await fetch(`${API_BASE_URL}/emails/status?user_id=${encodeURIComponent(email.trim())}`);
              if (verifyRes.ok) {
                const verifyData = await verifyRes.json();
                if (!verifyData.connections || !verifyData.connections.google) {
                  setLoading(false);
                  setError("Authentication was cancelled or failed. Cannot proceed with email searching.");
                  return; // STOP execution entirely
                }
              }
            } catch (e) {
              console.warn("Post-popup verification failed", e);
            }
          } else if (authPopup) {
            authPopup.close(); // Close if we failed to get redirect URL
          }
        } else if (authPopup) {
          authPopup.close(); // Close if auth fetch failed
        }
      } catch (err) {
        console.warn("OAuth flow failed, proceeding anyway...", err);
        if (authPopup) authPopup.close();
      }
    }
    // --- END JUST IN TIME OAUTH FLOW ---

    const formData = new FormData();
    formData.append('file', file);
    if (email.trim()) {
      formData.append('email', email.trim());
    }

    try {
      const res = await fetch(`${API_BASE_URL}/analyze-certificate`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP Error ${res.status}`);
      }

      const data = await res.json();
      setResponse(data);
      setCurrentStep(6); // Final success state

      // Fetch OCR preview from backend temp file
      try {
        const ocrRes = await fetch(`${API_BASE_URL}/ocr-preview`);
        if (ocrRes.ok) {
          const ocrData = await ocrRes.json();
          setOcrPreview(ocrData);
        }
      } catch (_) {
        // Non-critical — OCR preview is optional
      }

    } catch (err) {
      setError(err.message || 'An error occurred during pipeline analysis.');
      setCurrentStep(0);
    } finally {
      setLoading(false);
    }
  };

  const copyJsonToClipboard = () => {
    if (!response) return;
    navigator.clipboard.writeText(JSON.stringify(response, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyOcrText = () => {
    if (!ocrPreview?.raw_text) return;
    navigator.clipboard.writeText(ocrPreview.raw_text);
    setOcrCopied(true);
    setTimeout(() => setOcrCopied(false), 2000);
  };

  const clearCache = async () => {
    setClearCacheStatus('clearing');
    try {
      const res = await fetch(`${API_BASE_URL}/clear-cache`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Cache clear failed');
      const data = await res.json();
      setClearCacheStatus('done');
      setResponse(null);
      setOcrPreview(null);
      setCurrentStep(0);
      setTimeout(() => setClearCacheStatus(null), 3000);
    } catch (err) {
      setClearCacheStatus('error');
      setTimeout(() => setClearCacheStatus(null), 3000);
    }
  };

  const downloadOcrText = () => {
    if (!ocrPreview?.raw_text) return;
    const blob = new Blob([
      `=== OCR PREVIEW ===\nSource File  : ${ocrPreview.source_file}\nMethod Used  : ${ocrPreview.method}\n${'='.repeat(40)}\n\n${ocrPreview.raw_text}`
    ], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ocr_preview.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-container">
          <Award className="logo-icon" size={32} />
          <div>
            <h1 className="logo-text">Agentic OCR</h1>
            <span className="logo-subtext">Event Intelligence Core</span>
          </div>
        </div>

        {/* Global Tab Switcher Hidden per user request to avoid extra pages */}
        <div className="view-selector" style={{ display: 'none' }}>
          <button 
            type="button"
            className={`view-btn ${activeView === 'certificate' ? 'active' : ''}`}
            onClick={() => setActiveView('certificate')}
          >
            <Award size={15} />
            Certificate OCR Engine
          </button>
          <button 
            type="button"
            className={`view-btn ${activeView === 'semantic_search' ? 'active' : ''}`}
            onClick={() => setActiveView('semantic_search')}
          >
            <Mail size={15} />
            AI Email Intelligence Hub
          </button>
        </div>

        <div className="status-badge">
          <span className="status-dot"></span>
          Engine Active
        </div>
      </header>

      {activeView === 'certificate' ? (
        /* Original Dashboard Grid */
        <div className="dashboard-grid">
          
          {/* Left Hand side inputs & status */}
          <div className="left-panel">
            <div className="glass-card">
              <form onSubmit={analyzeDocument}>
                
                {/* Drag Drop Canvas */}
                <div 
                  className={`upload-zone ${dragActive ? 'drag-active' : ''}`}
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current.click()}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    className="file-input"
                    onChange={handleFileChange}
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
                    style={{ display: 'none' }}
                  />
                  
                  <div className="upload-icon-wrapper">
                    <Upload size={28} />
                  </div>
                  
                  <div>
                    <h3 className="upload-title">Drag & drop your certificate</h3>
                    <p className="upload-subtext">Supports PNG, JPG, JPEG, WEBP, PDF, and TXT (Max 10MB)</p>
                    <p className="upload-subtext" style={{ marginTop: '0.4rem', color: 'var(--accent-blue)', fontWeight: '600' }}>
                      Or click here / press Ctrl+V to paste an image!
                    </p>
                  </div>
                </div>

                {/* File Attachment Feedback */}
                {file && (
                  <div className="file-badge">
                    <div className="file-info">
                      <FileText size={18} className="logo-icon" />
                      <span>{file.name}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                      </span>
                    </div>
                    <button type="button" className="file-remove" onClick={removeFile}>
                      <X size={16} />
                    </button>
                  </div>
                )}

                {/* Dynamic Email Filter Input */}
                <div className="input-section">
                  <label className="input-label">
                    <Mail size={16} />
                    Recipient Email Filter (Optional)
                  </label>
                  <div className="input-wrapper">
                    <Mail className="input-icon" size={16} />
                    <input 
                      type="email" 
                      placeholder="Enter email address to filter mailbox lookups..." 
                      className="email-field"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={loading}
                    />
                  </div>
                </div>

                {/* Error Box */}
                {error && (
                  <div className="file-badge" style={{ borderColor: '#ef4444', background: 'rgba(239, 68, 68, 0.08)', marginTop: '1.25rem' }}>
                    <div className="file-info" style={{ color: '#f87171' }}>
                      <AlertCircle size={18} />
                      <span>{error}</span>
                    </div>
                  </div>
                )}

                {/* Trigger button */}
                <button 
                  type="submit" 
                  className="submit-btn"
                  disabled={loading || !file}
                >
                  {loading ? (
                    <>
                      <Server className="loader-spinner" style={{ animation: 'spin 1s infinite linear' }} size={18} />
                      Processing Autonomous Engine...
                    </>
                  ) : (
                    <>
                      <Sparkles size={18} />
                      Analyze & Enrich Certificate
                    </>
                  )}
                </button>

                {/* Clear Cache button */}
                <button
                  type="button"
                  onClick={clearCache}
                  disabled={loading || clearCacheStatus === 'clearing'}
                  style={{
                    width: '100%',
                    marginTop: '0.65rem',
                    padding: '0.6rem 1rem',
                    background: clearCacheStatus === 'done'
                      ? 'rgba(34,197,94,0.12)'
                      : clearCacheStatus === 'error'
                        ? 'rgba(239,68,68,0.1)'
                        : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${
                      clearCacheStatus === 'done' ? 'rgba(34,197,94,0.4)'
                      : clearCacheStatus === 'error' ? 'rgba(239,68,68,0.4)'
                      : 'rgba(255,255,255,0.1)'}`,
                    borderRadius: '10px',
                    color: clearCacheStatus === 'done' ? '#4ade80'
                      : clearCacheStatus === 'error' ? '#f87171'
                      : 'var(--text-secondary)',
                    fontSize: '0.82rem',
                    fontWeight: '600',
                    cursor: (loading || clearCacheStatus === 'clearing') ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                    transition: 'all 0.2s ease',
                    opacity: (loading || clearCacheStatus === 'clearing') ? 0.5 : 1,
                  }}
                >
                  <Trash2 size={14} />
                  {clearCacheStatus === 'clearing' ? 'Clearing Cache...'
                    : clearCacheStatus === 'done' ? 'Cache Cleared — Ready for Fresh Analysis'
                    : clearCacheStatus === 'error' ? 'Clear Failed — Try Again'
                    : 'Clear Analysis Cache (Force Fresh OCR)'}
                </button>

              </form>
            </div>

            {/* Real-time Pipeline Execution tracker */}
            <div className="glass-card pipeline-section">
              <h4 className="pipeline-header">
                <Brain size={18} />
                Autonomous Execution Chain
              </h4>
              
              <div className="steps-list">
                {steps.map((step) => {
                  let statusClass = 'pending';
                  if (currentStep >= step.num) statusClass = 'completed';
                  else if (currentStep === step.num - 1 && loading) statusClass = 'active';

                  return (
                    <div className={`step-row ${statusClass}`} key={step.num}>
                      <div className="step-circle">
                        {statusClass === 'completed' ? (
                          <CheckCircle2 size={18} />
                        ) : (
                          `0${step.num}`
                        )}
                      </div>
                      <div className="step-details">
                        <span className="step-name">{step.name}</span>
                        <span className="step-desc">{step.desc}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Right Hand Side results tabs and presentation panels */}
          <div className="right-panel">
            <div className="glass-card results-wrapper">
              <div className="results-bar">
                <div className="tabs">
                  <button 
                    className={`tab-btn ${activeTab === 'visual' ? 'active' : ''}`}
                    onClick={() => setActiveTab('visual')}
                    disabled={!response}
                  >
                    <Sparkles size={16} />
                    Synthesized Intel
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === 'email' ? 'active' : ''}`}
                    onClick={() => setActiveTab('email')}
                    disabled={!response}
                  >
                    <Mail size={16} />
                    Email linkage
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === 'ocr' ? 'active' : ''}`}
                    onClick={() => setActiveTab('ocr')}
                    disabled={!response}
                  >
                    <ScanText size={16} />
                    OCR Raw Text
                  </button>
                  <button 
                    className={`tab-btn ${activeTab === 'raw' ? 'active' : ''}`}
                    onClick={() => setActiveTab('raw')}
                    disabled={!response}
                  >
                    <FileText size={16} />
                    Playground JSON
                  </button>
                </div>
                
                {response && (
                  <div className="perf-timer">
                    <Clock size={12} style={{ marginRight: '4px', display: 'inline' }} />
                    Execution: {response.execution_time_seconds.toFixed(2)}s {response.cached ? '(Cached)' : ''}
                  </div>
                )}
              </div>

              {/* Empty Awaiting state */}
              {!loading && !response && (
                <div className="empty-state">
                  <div className="empty-icon-box">
                    <Brain size={32} />
                  </div>
                  <h4>Awaiting Document Upload</h4>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    Upload a certificate image or PDF and submit the request to initiate the multi-modal enrichment execution.
                  </p>
                </div>
              )}

              {/* Loader box */}
              {loading && !response && (
                <div className="loader-box">
                  <div className="loader-spinner"></div>
                  <div style={{ textAlign: 'center' }}>
                    <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.25rem' }}>Extracting Information...</h4>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Running PaddleOCR, Tavily, and LLM synthesis.
                    </p>
                  </div>
                </div>
              )}

              {/* Response Deck Presentation */}
              {response && !loading && (
                <div className="tab-content">
                  
                  {/* 1. VISUAL INTELLIGENCE PANEL */}
                  {activeTab === 'visual' && (
                    <div className="deck-section">
                      
                      {/* Metadata Card */}
                      <div className="deck-item" style={{ borderLeft: '4px solid var(--accent-blue)' }}>
                        <h4 className="deck-label">Certificate OCR Metadata</h4>
                        <h3 className="deck-value-large" style={{ color: '#38bdf8', marginBottom: '0.5rem' }}>
                          {response.certificate_data.certificate_name}
                        </h3>
                        
                        <div className="deck-row" style={{ marginTop: '1rem' }}>
                          <div>
                            <span className="deck-label">Recipient Name</span>
                            <div className="deck-value">{response.certificate_data.recipient}</div>
                          </div>
                          <div>
                            <span className="deck-label">Issuing Organization</span>
                            <div className="deck-value">{response.certificate_data.issuer}</div>
                          </div>
                        </div>

                        <div className="deck-row" style={{ marginTop: '1rem' }}>
                          <div>
                            <span className="deck-label">Issue Date</span>
                            <div className="deck-value" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Calendar size={14} />
                              {response.certificate_data.date}
                            </div>
                          </div>
                          <div>
                            <span className="deck-label">Pipeline Confidence</span>
                            <div className="deck-value" style={{ color: 'var(--accent-green)' }}>
                              {(response.confidence_score * 100).toFixed(0)}%
                            </div>
                            <div className="confidence-bar-container">
                              <div className="confidence-bar" style={{ width: `${response.confidence_score * 100}%` }}></div>
                            </div>
                          </div>
                        </div>

                        {response.certificate_data.skills && response.certificate_data.skills.length > 0 && (
                          <div style={{ marginTop: '1rem' }}>
                            <span className="deck-label">Extracted Skill Tags</span>
                            <div className="tag-list">
                              {response.certificate_data.skills.map((skill, i) => (
                                <span className="skill-tag" key={i}>{skill}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* 3-Way Event Intelligence Card */}
                      <div className="deck-item" style={{ borderLeft: '4px solid var(--accent-purple)' }}>
                        <h4 className="deck-label">Consolidated Event Intelligence (3-Way Merge)</h4>
                        
                        <div className="deck-row">
                          <div>
                            <span className="deck-label">Organized / Taught By</span>
                            <div className="deck-value">{response.event_intelligence.conducted_by}</div>
                          </div>
                          <div>
                            <span className="deck-label">Location / Platform</span>
                            <div className="deck-value" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <MapPin size={14} />
                              {response.event_intelligence.location}
                            </div>
                          </div>
                        </div>

                        <div className="deck-row" style={{ marginTop: '1rem' }}>
                          <div>
                            <span className="deck-label">Event Date Coordinates</span>
                            <div className="deck-value">{response.event_intelligence.date}</div>
                          </div>
                          <div>
                            <span className="deck-label">Hours / Time Coordinates</span>
                            <div className="deck-value">{response.event_intelligence.time}</div>
                          </div>
                        </div>

                        <div style={{ marginTop: '1rem' }}>
                          <span className="deck-label">Event Purpose & Learning Goals</span>
                          <p className="deck-text" style={{ color: 'var(--text-primary)', fontWeight: '500' }}>
                            {response.event_intelligence.purpose}
                          </p>
                        </div>

                        <div style={{ marginTop: '1rem' }}>
                          <span className="deck-label">Merged Event Description</span>
                          <p className="deck-text">{response.event_intelligence.description}</p>
                        </div>
                      </div>

                    </div>
                  )}

                  {/* 2. EMAIL LINKAGE INFORMATION PANEL */}
                  {activeTab === 'email' && (
                    <div className="deck-section">
                      <div 
                        className="deck-item" 
                        style={{ 
                          borderLeft: response.email_intelligence.matched_email ? '4px solid var(--accent-green)' : '4px solid var(--text-muted)' 
                        }}
                      >
                        {response.email_intelligence.matched_email ? (
                          <div>
                            <div className="deck-row">
                              <div>
                                <span className="deck-label">Email Sender</span>
                                <div className="deck-value">{response.email_intelligence.email_sender}</div>
                              </div>
                              <div>
                                <span className="deck-label">Date & Time Received</span>
                                <div className="deck-value" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                  <Calendar size={14} />
                                  {response.email_intelligence.email_date}
                                </div>
                              </div>
                            </div>

                            <div style={{ marginTop: '1.25rem' }}>
                              <span className="deck-label">Email Subject</span>
                              <div className="deck-value-large" style={{ color: 'var(--accent-green)', fontWeight: '600' }}>
                                {response.email_intelligence.email_subject}
                              </div>
                            </div>

                            <div style={{ marginTop: '1.25rem' }}>
                              <span className="deck-label">Email Contents</span>
                              <pre className="deck-text" style={{ 
                                padding: '1rem', 
                                background: 'rgba(0, 0, 0, 0.25)', 
                                borderRadius: '8px', 
                                whiteSpace: 'pre-wrap', 
                                wordBreak: 'break-word', 
                                fontFamily: 'inherit',
                                fontSize: '0.88rem',
                                lineHeight: '1.6',
                                color: 'var(--text-primary)',
                                border: '1px solid rgba(255, 255, 255, 0.05)'
                              }}>
                                {response.email_intelligence.email_body || response.email_intelligence.extracted_event_details}
                              </pre>
                            </div>
                          </div>
                        ) : (
                          <div style={{ padding: '1rem 0', color: 'var(--text-secondary)' }}>
                            <AlertCircle size={32} style={{ color: 'var(--text-muted)', marginBottom: '0.75rem' }} />
                            <h4 style={{ color: 'var(--text-primary)' }}>Email Linkage Status</h4>
                            <p style={{ fontSize: '0.85rem', marginTop: '0.4rem', lineHeight: '1.5', marginBottom: '1rem' }}>
                              {response.email_intelligence.warning_message || "No matching email was found."}
                            </p>
                            <button 
                              type="button" 
                              className="auth-action-btn"
                              style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', background: 'var(--accent-blue)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                              onClick={() => {
                                const targetEmail = email.trim() || window.prompt("Enter your Gmail address to connect:");
                                if (targetEmail) {
                                  handleConnectOAuth('google', targetEmail);
                                }
                              }}
                            >
                              <Mail size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
                              Connect to Gmail
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 3. OCR RAW TEXT PANEL */}
                  {activeTab === 'ocr' && (
                    <div className="deck-section">
                      <div className="deck-item" style={{ borderLeft: '4px solid #f59e0b' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <h4 className="deck-label" style={{ margin: 0 }}>
                            <ScanText size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                            Raw OCR Text Extraction
                          </h4>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                              type="button"
                              className="copy-btn"
                              style={{ position: 'static', padding: '0.4rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem' }}
                              onClick={copyOcrText}
                              title="Copy OCR text"
                            >
                              {ocrCopied ? <Check size={14} style={{ color: 'var(--accent-green)' }} /> : <Copy size={14} />}
                              {ocrCopied ? 'Copied!' : 'Copy'}
                            </button>
                            <button
                              type="button"
                              className="copy-btn"
                              style={{ position: 'static', padding: '0.4rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem' }}
                              onClick={downloadOcrText}
                              title="Download OCR text as .txt file"
                            >
                              <Download size={14} />
                              Download .txt
                            </button>
                          </div>
                        </div>

                        {ocrPreview ? (
                          <>
                            {/* Method Badge */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                              <div style={{
                                display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                                background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.35)',
                                borderRadius: '6px', padding: '0.3rem 0.75rem', fontSize: '0.8rem', color: '#fbbf24', fontWeight: '600'
                              }}>
                                <ScanText size={13} />
                                Method: {ocrPreview.method}
                              </div>
                              <div style={{
                                display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                                background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)',
                                borderRadius: '6px', padding: '0.3rem 0.75rem', fontSize: '0.78rem', color: '#a5b4fc'
                              }}>
                                <FileText size={13} />
                                {ocrPreview.source_file}
                              </div>
                            </div>

                            {/* Temp file path notice */}
                            <div style={{
                              display: 'flex', alignItems: 'center', gap: '0.5rem',
                              background: 'rgba(0,0,0,0.25)', borderRadius: '6px',
                              padding: '0.5rem 0.75rem', marginBottom: '1rem',
                              fontSize: '0.74rem', color: 'var(--text-muted)', fontFamily: 'monospace'
                            }}>
                              <FolderOpen size={13} style={{ flexShrink: 0 }} />
                              <span style={{ wordBreak: 'break-all' }}>
                                Temp file: {ocrPreview.temp_file_path}
                                <span style={{ marginLeft: '0.5rem', color: '#f87171', fontFamily: 'sans-serif', fontWeight: '600' }}>
                                  (auto-deleted on next search)
                                </span>
                              </span>
                            </div>

                            {/* Raw text viewer */}
                            <pre style={{
                              background: 'rgba(0,0,0,0.3)', borderRadius: '8px',
                              padding: '1rem', fontSize: '0.8rem',
                              color: '#e2e8f0', fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                              maxHeight: '420px', overflowY: 'auto',
                              lineHeight: '1.6', border: '1px solid rgba(245, 158, 11, 0.15)'
                            }}>
                              {ocrPreview.raw_text || '(No text was extracted from this file)'}
                            </pre>
                          </>
                        ) : (
                          <div style={{ padding: '2rem 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            <ScanText size={32} style={{ color: 'var(--text-muted)', marginBottom: '0.75rem' }} />
                            <p style={{ fontSize: '0.85rem' }}>OCR preview not available.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 4. RAW JSON PLAYGROUND PANEL */}
                  {activeTab === 'raw' && (
                    <div className="code-container">
                      <button type="button" className="copy-btn" onClick={copyJsonToClipboard} title="Copy Raw Response">
                        {copied ? <Check size={16} style={{ color: 'var(--accent-green)' }} /> : <Copy size={16} />}
                      </button>
                      <pre className="code-pre">
                        {JSON.stringify(response, null, 2)}
                      </pre>
                    </div>
                  )}

                </div>
              )}
            </div>
          </div>

        </div>
      ) : (
        /* Email Intelligence Hub Dashboard Grid */
        <div className="dashboard-grid email-hub-grid">
          
          {/* Left Panel: Connections & Sync Monitor */}
          <div className="left-panel">
            <div className="glass-card">
              <h4 className="pipeline-header">
                <Database size={18} />
                Secure Mailbox Links (OAuth 2.0)
              </h4>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.25rem', marginBottom: '1.25rem', lineHeight: '1.5' }}>
                Establish isolated, multi-tenant encrypted endpoints to index email text layers securely into Qdrant vector database.
              </p>

              {/* User Identity Key */}
              <div className="input-section" style={{ marginTop: '0.5rem' }}>
                <label className="input-label">
                  <Database size={15} />
                  User Email Tenant Namespace Key
                </label>
                <div className="input-wrapper">
                  <Mail className="input-icon" size={16} />
                  <input 
                    type="email" 
                    placeholder="Enter email to index (e.g. alex@example.com)" 
                    className="email-field"
                    value={userEmail}
                    onChange={(e) => {
                      setUserEmail(e.target.value);
                      setSearchResults(null);
                    }}
                  />
                </div>
              </div>

              {/* Integrations */}
              <div className="integrations-list" style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                
                {/* Google */}
                <div className="integration-row">
                  <div className="integration-info">
                    <div className="provider-logo google">G</div>
                    <div className="integration-meta">
                      <span className="integration-name">Google Mailbox (Gmail)</span>
                      <span className="integration-status">
                        {syncStatus?.connections?.google 
                          ? `Linked: ${syncStatus.connections.google.email}` 
                          : 'Not connected (Offline Dev Mode Available)'}
                      </span>
                    </div>
                  </div>
                  <div className="integration-actions">
                    <button 
                      type="button" 
                      className="auth-action-btn"
                      onClick={() => handleConnectOAuth('google')}
                    >
                      Connect
                    </button>
                    <button 
                      type="button" 
                      className="sync-action-btn"
                      disabled={!syncStatus?.connections?.google || syncLoading}
                      onClick={() => handleTriggerSync('google')}
                    >
                      Sync
                    </button>
                  </div>
                </div>

                {/* Microsoft */}
                <div className="integration-row">
                  <div className="integration-info">
                    <div className="provider-logo microsoft">M</div>
                    <div className="integration-meta">
                      <span className="integration-name">Microsoft Outlook (Graph)</span>
                      <span className="integration-status">
                        {syncStatus?.connections?.microsoft 
                          ? `Linked: ${syncStatus.connections.microsoft.email}` 
                          : 'Not connected (Offline Dev Mode Available)'}
                      </span>
                    </div>
                  </div>
                  <div className="integration-actions">
                    <button 
                      type="button" 
                      className="auth-action-btn microsoft"
                      onClick={() => handleConnectOAuth('microsoft')}
                    >
                      Connect
                    </button>
                    <button 
                      type="button" 
                      className="sync-action-btn microsoft"
                      disabled={!syncStatus?.connections?.microsoft || syncLoading}
                      onClick={() => handleTriggerSync('microsoft')}
                    >
                      Sync
                    </button>
                  </div>
                </div>

              </div>

              {/* Dev mode note */}
              <div className="dev-mode-note" style={{
                marginTop: '1.25rem',
                padding: '0.8rem',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-glass)',
                borderRadius: '10px',
                fontSize: '0.76rem',
                color: 'var(--text-muted)',
                lineHeight: '1.5'
              }}>
                <span style={{ color: 'var(--accent-blue)', fontWeight: '600', display: 'block', marginBottom: '0.2rem' }}>💡 Developer Sandbox Mode Active</span>
                No local config variables? Pressing <strong>Connect</strong> triggers an offline mock flow that connects a sandbox inbox immediately, generating realistic mock certificate emails for robust indexing and semantic RAG queries.
              </div>

              {/* Error messages */}
              {emailHubError && (
                <div className="file-badge" style={{ borderColor: '#ef4444', background: 'rgba(239, 68, 68, 0.08)', marginTop: '1.25rem' }}>
                  <div className="file-info" style={{ color: '#f87171' }}>
                    <AlertCircle size={18} />
                    <span>{emailHubError}</span>
                  </div>
                </div>
              )}

              {/* GDPR Wipe */}
              {syncStatus && (syncStatus.email_count > 0 || Object.keys(syncStatus.connections).length > 0) && (
                <button 
                  type="button" 
                  className="wipe-btn"
                  onClick={handleWipeData}
                  disabled={gdprWiping}
                  style={{
                    width: '100%',
                    marginTop: '1.25rem',
                    padding: '0.8rem',
                    background: 'rgba(239, 68, 68, 0.05)',
                    border: '1px dashed rgba(239, 68, 68, 0.4)',
                    borderRadius: '10px',
                    color: '#f87171',
                    fontWeight: '600',
                    fontSize: '0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Trash2 size={14} />
                  {gdprWiping ? 'Wiping tenant store...' : 'GDPR Compliance: Wipe and Revoke Namespace'}
                </button>
              )}
            </div>

            {/* Ingestion Monitor Card */}
            <div className="glass-card pipeline-section">
              <h4 className="pipeline-header">
                <Database size={18} />
                Tenant Database Monitor
              </h4>

              <div className="db-stats-bar">
                <div className="stat-card">
                  <span className="stat-label">Indexed Emails</span>
                  <span className="stat-val">{syncStatus?.email_count ?? 0}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Active Links</span>
                  <span className="stat-val">{Object.keys(syncStatus?.connections ?? {}).length}</span>
                </div>
              </div>

              <h5 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.5px', marginTop: '0.5rem', marginBottom: '0.25rem', fontWeight: '700' }}>
                Inbox Sync Timeline Logs
              </h5>

              {(!syncStatus || !syncStatus.sync_history || syncStatus.sync_history.length === 0) ? (
                <div className="empty-logs">
                  <Clock size={20} style={{ opacity: 0.5, color: 'var(--text-muted)' }} />
                  <span>No sync logs found. Connect an inbox and trigger sync to index data.</span>
                </div>
              ) : (
                <div className="logs-scrollable">
                  <div className="logs-timeline">
                    {syncStatus.sync_history.map((log) => (
                      <div className="log-row" key={log.id}>
                        <div className={`log-indicator ${log.status}`}></div>
                        <div className="log-body">
                          <div className="log-header-row">
                            <span className="log-provider">{log.provider.toUpperCase()} INBOX</span>
                            <span className="log-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
                          </div>
                          <div className="log-details-row">
                            <span className="log-status-text">
                              Status: <strong className={`status-${log.status}`}>{log.status}</strong>
                            </span>
                            {log.status === 'completed' && (
                              <span className="log-synced-count">
                                Synced: <strong>{log.emails_synced} fresh emails</strong>
                              </span>
                            )}
                            {log.status === 'running' && (
                              <span className="log-synced-count" style={{ color: 'var(--accent-blue)' }}>
                                Synced: <strong>running sync...</strong>
                              </span>
                            )}
                            {log.status === 'failed' && (
                              <span className="log-error-text" title={log.error_message}>
                                Error: {log.error_message?.slice(0, 30)}...
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel: Search Workspace & RAG Results */}
          <div className="right-panel">
            <div className="glass-card">
              <h4 className="pipeline-header" style={{ color: 'var(--accent-blue)', marginBottom: '0.25rem' }}>
                <Sparkles size={18} />
                Semantic Inbox Exploration (RAG)
              </h4>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: '1.5' }}>
                Query your synchronized mailboxes with natural language. Dense vector math and LLM context extraction will retrieve key events.
              </p>

              <form onSubmit={handleSemanticSearch} className="search-hub-form">
                <div className="search-mode-toggles">
                  <button 
                    type="button" 
                    className={`mode-toggle-btn ${searchMode === 'rag' ? 'active' : ''}`}
                    onClick={() => setSearchMode('rag')}
                  >
                    <Sparkles size={14} />
                    AI Conversational RAG
                  </button>
                  <button 
                    type="button" 
                    className={`mode-toggle-btn ${searchMode === 'vector' ? 'active' : ''}`}
                    onClick={() => setSearchMode('vector')}
                  >
                    <Cpu size={14} />
                    Dense Vector Hits
                  </button>
                </div>

                <div className="input-wrapper search-wrapper">
                  <Search className="input-icon search-icon" size={18} />
                  <input 
                    type="text" 
                    placeholder={
                      searchMode === 'rag' 
                        ? "Ask natural questions, e.g. 'What AWS certification did I complete?'" 
                        : "Search key concepts, e.g. 'World Journal Advanced Research'"
                    } 
                    className="search-field"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <button 
                    type="submit" 
                    className="search-execute-btn"
                    disabled={searchLoading || !searchQuery.trim()}
                  >
                    {searchLoading ? <RefreshCw className="loader-spinner animate-spin" size={16} /> : <ChevronRight size={16} />}
                  </button>
                </div>

                <div className="slider-container" style={{ marginTop: '0.85rem' }}>
                  <span className="slider-label">
                    Context Retrieval Size Limit: <strong>{searchLimit} emails</strong>
                  </span>
                  <input 
                    type="range" 
                    min="1" 
                    max="10" 
                    className="slider-input" 
                    value={searchLimit} 
                    onChange={(e) => setSearchLimit(e.target.value)}
                  />
                </div>
              </form>
            </div>

            {/* Results Presentation Container */}
            <div className="glass-card results-wrapper" style={{ marginTop: '1.5rem', minHeight: '380px' }}>
              
              {/* Search Loading */}
              {searchLoading && (
                <div className="loader-box" style={{ padding: '4rem 0' }}>
                  <div className="loader-spinner"></div>
                  <div style={{ textAlign: 'center' }}>
                    <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.25rem' }}>Retrieving Email Nodes...</h4>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Generating query embedding, filtering Qdrant, and running RAG synthesis...
                    </p>
                  </div>
                </div>
              )}

              {/* Empty/Awaiting Search State */}
              {!searchLoading && !searchResults && (
                <div className="empty-state" style={{ padding: '4rem 0' }}>
                  <div className="empty-icon-box" style={{ color: 'var(--accent-blue)', borderColor: 'rgba(59, 130, 246, 0.2)' }}>
                    <Brain size={32} />
                  </div>
                  <h4>Awaiting Natural Language Query</h4>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    Make sure your inbox has been synced, then type a search query above to explore.
                  </p>
                </div>
              )}

              {/* Search results presentation */}
              {!searchLoading && searchResults && (
                <div className="tab-content" style={{ animation: 'fadeIn 0.4s ease' }}>
                  
                  {/* RAG summary answer */}
                  {searchMode === 'rag' && searchResults.summary && (
                    <div className="rag-answer-card">
                      <h4 className="rag-answer-header">
                        <Sparkles size={15} style={{ color: 'var(--accent-purple)', display: 'inline', marginRight: '6px' }} />
                        Synthesized AI Conversational Answer
                      </h4>
                      <div className="rag-answer-body">
                        {renderFormattedSummary(searchResults.summary)}
                      </div>
                    </div>
                  )}

                  {/* Matching Node list */}
                  <div className="matches-list-container" style={{ marginTop: searchMode === 'rag' ? '1.5rem' : '0' }}>
                    <h5 style={{ fontSize: '0.82rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.5px', marginBottom: '0.75rem', fontWeight: '700' }}>
                      Semantic Similarity Matches ({searchResults.matches?.length ?? 0} hits)
                    </h5>
                    
                    {(!searchResults.matches || searchResults.matches.length === 0) ? (
                      <div className="empty-state" style={{ padding: '2rem 0' }}>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          No relevant emails or matching vector nodes found in Qdrant namespace.
                        </p>
                      </div>
                    ) : (
                      <div className="matches-grid">
                        {searchResults.matches.map((match, i) => (
                          <div className="match-card" key={i}>
                            <div className="match-card-header">
                              <div className="match-sender-group">
                                <span className="match-sender-indicator"></span>
                                <span className="match-sender" title={match.sender}>
                                  {match.sender?.split('<')[0]?.trim() || match.sender}
                                </span>
                              </div>
                              <span className="match-score-badge">
                                {match.score ? `${Math.round(match.score * 100)}% Match` : 'Linked'}
                              </span>
                            </div>
                            <h5 className="match-subject">{match.subject}</h5>
                            <p className="match-snippet">"{match.snippet}"</p>
                            <div className="match-card-footer">
                              <span className="match-date">{new Date(match.timestamp).toLocaleDateString()}</span>
                              <span className="match-thread-id">Thread: {match.thread_id?.slice(0, 10) || 'N/A'}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                </div>
              )}

            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
