import { useEffect, useState } from 'react'
import { config } from '../config.js'
import './App.css'

const API_BASE_URL = `http://localhost:${config.backendPort}`

const techniques = [
  { value: 'zero_shot', label: 'Zero-shot' },
  { value: 'few_shot', label: 'Few-shot' },
  { value: 'chain_of_thought', label: 'Chain of thought' },
  { value: 'role_prompting', label: 'Role prompting' },
]

const datasetExample = `{"id":"I001","language":"en","text":"I need a refund for a duplicate charge.","ground_truth":{"intent":"refund_request"},"annotator":"Name","notes":""}`

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.detail || `Request failed (${response.status})`)
  }
  return body
}

function App() {
  const [activeTab, setActiveTab] = useState('run')
  const [connection, setConnection] = useState('checking')
  const [experiments, setExperiments] = useState([])
  const [experimentsError, setExperimentsError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)
  const [expandedExperiment, setExpandedExperiment] = useState(null)
  const [experimentFiles, setExperimentFiles] = useState([])
  const [filesError, setFilesError] = useState('')
  const [datasets, setDatasets] = useState([])
  const [datasetsError, setDatasetsError] = useState('')
  const [datasetRefresh, setDatasetRefresh] = useState(0)
  const [selectedFile, setSelectedFile] = useState(null)
  const [notice, setNotice] = useState('')
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [form, setForm] = useState({
    dataset_path: '',
    techniques: techniques.map((technique) => technique.value),
    runs_per_technique: 3,
    model_name: '',
    temperature: 0.2,
    max_tokens: 120,
    top_p: 1,
  })

  useEffect(() => {
    let isActive = true

    async function refreshExperiments() {
      try {
        const data = await apiRequest('/experiments/list')
        if (!isActive) return
        setExperiments(data.experiments || [])
        setExperimentsError('')
        setConnection('connected')
      } catch (error) {
        if (!isActive) return
        setExperimentsError(error.message)
        try {
          await apiRequest('/health')
          if (isActive) setConnection('connected')
        } catch {
          if (isActive) setConnection('offline')
        }
      }
    }

    refreshExperiments()
    const timer = window.setInterval(refreshExperiments, 5000)
    return () => {
      isActive = false
      window.clearInterval(timer)
    }
  }, [refreshToken])

  useEffect(() => {
    let isActive = true
    apiRequest('/datasets/list')
      .then((data) => {
        if (isActive) {
          setDatasets(data.datasets || [])
          setDatasetsError('')
        }
      })
      .catch((error) => {
        if (isActive) setDatasetsError(error.message)
      })
    return () => {
      isActive = false
    }
  }, [datasetRefresh])

  useEffect(() => {
    if (!expandedExperiment) return undefined
    let isActive = true
    apiRequest(`/experiments/${encodeURIComponent(expandedExperiment)}/files`)
      .then((data) => {
        if (isActive) setExperimentFiles(data.files || [])
      })
      .catch((error) => {
        if (isActive) setFilesError(error.message)
      })
    return () => {
      isActive = false
    }
  }, [expandedExperiment])

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function toggleTechnique(value) {
    setForm((current) => ({
      ...current,
      techniques: current.techniques.includes(value)
        ? current.techniques.filter((technique) => technique !== value)
        : [...current.techniques, value],
    }))
  }

  async function submitExperiment(event) {
    event.preventDefault()
    setFormError('')
    setNotice('')
    if (form.techniques.length === 0) {
      setFormError('Select at least one prompting technique.')
      return
    }
    setIsSubmitting(true)
    try {
      const result = await apiRequest('/experiments/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_path: form.dataset_path || null,
          techniques: form.techniques,
          runs_per_technique: Number(form.runs_per_technique),
          model_name: form.model_name || null,
          params: {
            temperature: Number(form.temperature),
            max_tokens: Number(form.max_tokens),
            top_p: Number(form.top_p),
          },
        }),
      })
      setNotice(`Experiment ${result.experiment_id} queued.`)
      setActiveTab('experiments')
      setRefreshToken((token) => token + 1)
    } catch (error) {
      setFormError(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function uploadDataset(event) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    setDatasetsError('')
    setIsUploading(true)
    try {
      const payload = new FormData()
      payload.append('file', file)
      const result = await apiRequest('/datasets/upload', { method: 'POST', body: payload })
      setNotice(`Uploaded ${result.filename}.`)
      setDatasetRefresh((value) => value + 1)
    } catch (error) {
      setDatasetsError(error.message)
    } finally {
      setIsUploading(false)
    }
  }

  async function downloadExperimentFile(experimentId, filename) {
    setSelectedFile(`${experimentId}/${filename}`)
    setFilesError('')
    try {
      const query = new URLSearchParams({ filename })
      const result = await apiRequest(
        `/experiments/${encodeURIComponent(experimentId)}/download?${query}`,
      )
      const binary = window.atob(result.content_base64)
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
      const url = URL.createObjectURL(new Blob([bytes]))
      const link = document.createElement('a')
      link.href = url
      link.download = result.filename || filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setFilesError(error.message)
    } finally {
      setSelectedFile(null)
    }
  }

  async function deleteExperiment() {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await apiRequest(`/experiments/${encodeURIComponent(deleteTarget.experiment_id)}`, {
        method: 'DELETE',
      })
      setNotice(`Deleted ${deleteTarget.experiment_id}.`)
      if (expandedExperiment === deleteTarget.experiment_id) {
        setExpandedExperiment(null)
        setExperimentFiles([])
      }
      setDeleteTarget(null)
      setRefreshToken((token) => token + 1)
    } catch (error) {
      setExperimentsError(error.message)
    } finally {
      setIsDeleting(false)
    }
  }

  function formatDate(value) {
    if (!value) return 'Date unavailable'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#run" onClick={() => setActiveTab('run')}>
          <span className="brand-mark">P6</span>
          <span><strong>Prompting Lab</strong><small>LLM evaluation workspace</small></span>
        </a>
        <div className={`connection connection-${connection}`}>
          <span className="connection-dot" />
          {connection === 'checking' ? 'Connecting' : connection === 'connected' ? 'API connected' : 'API unavailable'}
        </div>
      </header>

      <nav className="tabs" aria-label="Workspace sections">
        <button className={activeTab === 'run' ? 'tab active' : 'tab'} onClick={() => setActiveTab('run')}>Run experiment</button>
        <button className={activeTab === 'experiments' ? 'tab active' : 'tab'} onClick={() => setActiveTab('experiments')}>
          Experiments <span className="tab-count">{experiments.length}</span>
        </button>
        <button className={activeTab === 'datasets' ? 'tab active' : 'tab'} onClick={() => setActiveTab('datasets')}>
          Datasets <span className="tab-count">{datasets.length}</span>
        </button>
      </nav>

      <div className="workspace">
        {notice && <div className="notice" role="status"><span>{notice}</span><button className="text-button" type="button" onClick={() => setNotice('')} aria-label="Dismiss notification">Dismiss</button></div>}

        {activeTab === 'run' && (
          <section className="view" aria-labelledby="run-title">
            <div className="view-heading">
              <p className="eyebrow">EXPERIMENT SETUP</p>
              <h1 id="run-title">Run an experiment</h1>
              <p className="subheading">Choose a dataset, prompting strategies, and model parameters.</p>
            </div>
            <form className="form-layout" onSubmit={submitExperiment}>
              <section className="form-section">
                <div className="section-heading"><span className="section-index">01</span><div><h2>Data and technique</h2><p>Set the evaluation input and comparison set.</p></div></div>
                <div className="field-grid">
                  <label className="field field-wide"><span>Dataset</span>
                    <select value={form.dataset_path} onChange={(event) => updateForm('dataset_path', event.target.value)}>
                      <option value="">Default dataset</option>
                      {datasets.map((dataset) => <option key={dataset.filename} value={dataset.filename}>{dataset.filename}</option>)}
                    </select>
                  </label>
                  <label className="field"><span>Runs per technique</span><input type="number" min="1" max="50" value={form.runs_per_technique} onChange={(event) => updateForm('runs_per_technique', event.target.value)} required /></label>
                </div>
                <fieldset className="technique-fieldset">
                  <legend>Prompting techniques</legend>
                  <div className="technique-grid">
                    {techniques.map((technique) => (
                      <label className="check-option" key={technique.value}>
                        <input type="checkbox" checked={form.techniques.includes(technique.value)} onChange={() => toggleTechnique(technique.value)} />
                        <span>{technique.label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              </section>

              <section className="form-section">
                <div className="section-heading"><span className="section-index">02</span><div><h2>Model configuration</h2><p>Parameters are recorded with the experiment.</p></div></div>
                <div className="field-grid">
                  <label className="field field-wide"><span>Model name</span><input type="text" value={form.model_name} onChange={(event) => updateForm('model_name', event.target.value)} placeholder="Use configured default" /></label>
                  <label className="field"><span>Temperature</span><input type="number" min="0" max="2" step="0.1" value={form.temperature} onChange={(event) => updateForm('temperature', event.target.value)} /></label>
                  <label className="field"><span>Max tokens</span><input type="number" min="1" max="32768" value={form.max_tokens} onChange={(event) => updateForm('max_tokens', event.target.value)} /></label>
                  <label className="field"><span>Top P</span><input type="number" min="0" max="1" step="0.05" value={form.top_p} onChange={(event) => updateForm('top_p', event.target.value)} /></label>
                </div>
              </section>
              {formError && <p className="error-message" role="alert">{formError}</p>}
              <div className="form-actions"><button className="primary-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Starting…' : 'Start experiment'}</button></div>
            </form>
          </section>
        )}

        {activeTab === 'experiments' && (
          <section className="view" aria-labelledby="experiments-title">
            <div className="view-heading heading-row"><div><p className="eyebrow">RUN HISTORY</p><h1 id="experiments-title">Experiments</h1><p className="subheading">Current and previous evaluation runs.</p></div>
              <button className="secondary-button" type="button" onClick={() => setRefreshToken((token) => token + 1)}>Refresh</button>
            </div>
            {experimentsError && <p className="error-message" role="alert">{experimentsError}</p>}
            {experiments.length === 0 && !experimentsError ? (
              <div className="empty-state"><h2>No experiments yet</h2><p>New runs will appear here with their status and output files.</p></div>
            ) : (
              <div className="experiment-list">
                {experiments.map((experiment) => {
                  const isExpanded = expandedExperiment === experiment.experiment_id
                  return (
                    <article className="experiment-item" key={experiment.experiment_id}>
                      <div className="experiment-row">
                        <div className="experiment-main">
                          <span className={`status-pill status-${experiment.status || 'unknown'}`}><span className="status-dot" />{experiment.status || 'unknown'}</span>
                          <div className="experiment-copy"><h2>{experiment.experiment_id}</h2><p>{formatDate(experiment.created_at)} <span className="meta-separator">/</span> {experiment.model_name || 'Default model'}</p></div>
                        </div>
                        <div className="experiment-meta"><span>{experiment.runs_per_technique || 0} runs</span><span>{(experiment.techniques || []).length} techniques</span>
                          <button className="secondary-button compact" type="button" onClick={() => {
                            setExperimentFiles([])
                            setFilesError('')
                            setExpandedExperiment(isExpanded ? null : experiment.experiment_id)
                          }}>{isExpanded ? 'Hide files' : 'Files'}</button>
                          <button className="danger-button compact" type="button" disabled={['pending', 'running'].includes(experiment.status)} title={['pending', 'running'].includes(experiment.status) ? 'Wait for this experiment to finish before deleting it.' : undefined} onClick={() => setDeleteTarget(experiment)}>Delete</button>
                        </div>
                      </div>
                      {isExpanded && <div className="file-panel">
                        <div className="file-panel-heading"><h3>Generated files</h3><span>{experimentFiles.length} files</span></div>
                        {filesError && <p className="error-message" role="alert">{filesError}</p>}
                        {experimentFiles.length === 0 && !filesError ? <p className="file-empty">No output files available yet.</p> : (
                          <ul className="file-list">{experimentFiles.map((file) => {
                            const fileKey = `${experiment.experiment_id}/${file.filename}`
                            return <li key={file.filename}><span className="file-name"><span className="file-mark">FILE</span>{file.filename}</span><span className="file-size">{(file.size / 1024).toFixed(file.size < 1024 ? 0 : 1)} KB</span>
                              <button className="text-button download-button" type="button" disabled={selectedFile === fileKey} onClick={() => downloadExperimentFile(experiment.experiment_id, file.filename)}>{selectedFile === fileKey ? 'Downloading…' : 'Download'}</button>
                            </li>
                          })}</ul>
                        )}
                      </div>}
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        )}

        {activeTab === 'datasets' && (
          <section className="view" aria-labelledby="datasets-title">
            <div className="view-heading heading-row"><div><p className="eyebrow">DATA MANAGEMENT</p><h1 id="datasets-title">Datasets</h1><p className="subheading">Upload a JSONL dataset or use one already available to the API.</p></div>
              <label className={`primary-button upload-button ${isUploading ? 'disabled' : ''}`}>{isUploading ? 'Uploading…' : 'Upload JSONL'}<input type="file" accept=".jsonl,.json,application/json" onChange={uploadDataset} disabled={isUploading} /></label>
            </div>
            {datasetsError && <p className="error-message" role="alert">{datasetsError}</p>}
            <section className="dataset-section">
              <div className="section-heading dataset-heading"><span className="section-index">01</span><div><h2>Available datasets</h2><p>{datasets.length} files on the backend</p></div></div>
              {datasets.length === 0 ? <div className="empty-state compact-empty"><p>No datasets found.</p></div> : (
                <ul className="dataset-list">{datasets.map((dataset) => <li key={dataset.filename}><span className="file-name"><span className="file-mark">JSONL</span>{dataset.filename}</span><span className="file-size">{(dataset.size / 1024).toFixed(dataset.size < 1024 ? 0 : 1)} KB</span></li>)}</ul>
              )}
            </section>
            <section className="dataset-section schema-section">
              <div className="section-heading dataset-heading"><span className="section-index">02</span><div><h2>Record format</h2><p>One JSON object per line. The intent label is used as ground truth.</p></div></div>
              <pre className="schema-code"><code>{datasetExample}</code></pre>
            </section>
          </section>
        )}
      </div>

      {deleteTarget && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isDeleting) setDeleteTarget(null) }}>
        <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description">
          <p className="eyebrow">DELETE EXPERIMENT</p><h2 id="delete-title">Delete this experiment?</h2>
          <p id="delete-description">This permanently removes <code>{deleteTarget.experiment_id}</code> and its generated files.</p>
          <div className="modal-actions"><button className="secondary-button" type="button" disabled={isDeleting} onClick={() => setDeleteTarget(null)}>Cancel</button><button className="danger-button" type="button" disabled={isDeleting} onClick={deleteExperiment}>{isDeleting ? 'Deleting…' : 'Delete experiment'}</button></div>
        </section>
      </div>}
    </main>
  )
}

export default App
