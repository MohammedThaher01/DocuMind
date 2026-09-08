import { useState } from 'react'

const API_BASE =
  (import.meta.env && import.meta.env.VITE_API_URL) ||
  'http://localhost:8000'

const SAMPLE_PROMPTS = [
  {
    label: 'Meeting Minutes',
    prompt:
      'Create meeting minutes for our weekly engineering standup. Attendees were Priya, Arjun and Neha. We discussed sprint progress, a bug in the payment module, and next sprint planning.',
  },
  {
    label: 'Client Proposal (Ambiguous)',
    prompt:
      'We need a proposal for a new client but I havent decided if this is a fixed-price or time-and-materials project yet, the client wants it delivered in 2 weeks but our team says 6 weeks minimum, and we dont have a budget number finalized. Just put something together.',
  },
  {
    label: 'Project Plan',
    prompt:
      'Write a project plan for migrating our legacy PHP monolith to a microservices architecture on AWS. Team of 6 engineers, C-level cares about risk and timeline.',
  },
  {
    label: 'SOP Document',
    prompt:
      'Create a standard operating procedure for onboarding a new customer support agent. Include tool access, training, shadowing, and the 30-60-90 day milestones.',
  },
]

const PRETTY_DOC_TYPE = {
  proposal: 'Client Proposal',
  meeting_minutes: 'Meeting Minutes',
  project_plan: 'Project Plan',
  business_report: 'Business Report',
  technical_design: 'Technical Design',
  sop: 'Standard Operating Procedure',
  product_spec: 'Product Spec',
}

function prettyDoc(type) {
  if (!type) return 'Document'
  return PRETTY_DOC_TYPE[type] || type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function statusBadge(status) {
  const map = {
    done:   ['bg-emerald-500/10 text-emerald-400 border-emerald-500/20', '✓'],
    pending:['bg-slate-500/10 text-slate-400 border-slate-500/20', ''],
    running:['bg-amber-500/10 text-amber-400 border-amber-500/20', '…'],
    failed: ['bg-rose-500/10 text-rose-400 border-rose-500/20', '✕'],
  }
  return map[status] || map.pending
}

export default function App() {
  const [request, setRequest] = useState(SAMPLE_PROMPTS[0].prompt)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const [status, setStatus] = useState(null)
  const [taskList, setTaskList] = useState([])
  const [assumptions, setAssumptions] = useState([])
  const [docType, setDocType] = useState('')
  const [critique, setCritique] = useState(null)
  const [result, setResult] = useState(null)

  const onSubmit = async (e) => {
    if (e) e.preventDefault()
    if (!request.trim() || submitting) return

    setSubmitting(true)
    setStatus('running')
    setError(null)
    setResult(null)
    setTaskList([])
    setAssumptions([])
    setDocType('')
    setCritique(null)

    try {
      const res = await fetch('/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: request.trim() }),
      })

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Request failed (${res.status})`)
      }

      const data = await res.json()

      setStatus('completed')
      setResult(data)
      setTaskList(data.task_list || [])
      setAssumptions(data.assumptions || [])
      setDocType(data.doc_type || '')
      if (data.critique) setCritique(data.critique)

      if (data.download_url) {
        window.location.href = data.download_url
      }
    } catch (err) {
      setStatus('failed')
      setError(err.message || String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const downloadUrl = result?.download_url || ''
  const active = submitting || Boolean(result) || taskList.length > 0 || Boolean(error)
  const charCount = request.length

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-200 font-sans selection:bg-brand-500/30">
      <header className="max-w-6xl mx-auto px-6 pt-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-500 flex items-center justify-center text-white shadow-soft">
            <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="13" x2="15" y2="13" />
              <line x1="9" y1="17" x2="15" y2="17" />
            </svg>
          </div>
          <div>
            <div className="font-extrabold text-lg tracking-tight text-slate-100">DocuMind</div>
          </div>
        </div>
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="hidden sm:inline-flex items-center gap-1.5 text-sm font-medium text-slate-400 hover:text-slate-100 transition"
        >
          API Docs
          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 17L17 7" /><path d="M7 7h10v10" />
          </svg>
        </a>
      </header>

      <main className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/10 text-brand-400 text-xs font-semibold px-3 py-1 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
            LangGraph · Groq · Self-reflecting agent
          </div>
          <h1 className="font-extrabold text-4xl sm:text-5xl tracking-tight text-slate-100 leading-[1.05]">
            Describe it. DocuMind{' '}
            <span className="bg-gradient-to-r from-brand-400 to-indigo-400 bg-clip-text text-transparent">
              plans, writes, critiques, and ships
            </span>{' '}
            the document.
          </h1>
          <p className="mt-5 text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Turn a plain-English business request into a polished Word document.
            The agent classifies the document type, fills in gaps with stated
            assumptions, drafts section-by-section, self-critiques, revises,
            and exports a .docx automatically.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-10">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 shadow-soft p-5 sm:p-6">
            <label htmlFor="request" className="block text-sm font-semibold text-slate-200 mb-2">
              What document do you need?
            </label>
            <textarea
              id="request"
              rows={5}
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="e.g. Create a product spec for an AI-powered mobile expense tracker..."
              className="block w-full resize-none rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 text-slate-100 placeholder-slate-500 text-[15px] leading-relaxed outline-none ring-brand-500/20 focus:bg-slate-900 focus:border-brand-500/50 focus:ring-4 transition"
              maxLength={4000}
              disabled={submitting}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-slate-500">
                <span className={charCount > 3800 ? 'text-amber-500 font-medium' : ''}>{charCount}</span>
                <span className="opacity-60"> / 4000 chars</span>
              </div>
              <button
                type="submit"
                disabled={submitting || !request.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-brand-600 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-soft hover:from-brand-500 hover:to-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed transition"
              >
                {submitting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                    Generating...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                    </svg>
                    Generate .docx
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="mt-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2.5">Try an example</div>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_PROMPTS.map((s) => (
                <button
                  type="button"
                  key={s.label}
                  onClick={() => !submitting && setRequest(s.prompt)}
                  disabled={submitting}
                  className="rounded-full border border-slate-800 bg-slate-900 text-sm px-3.5 py-1.5 text-slate-300 hover:border-brand-500/50 hover:text-brand-300 hover:bg-brand-900/20 disabled:opacity-60 transition"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </form>

        {error && (
          <div className="mt-8 rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-400 flex items-start gap-3">
            <svg viewBox="0 0 24 24" className="w-5 h-5 mt-0.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <div>
              <div className="font-semibold">Something went wrong</div>
              <div className="opacity-90 mt-0.5">{error}</div>
            </div>
          </div>
        )}

        {active && (
          <section className="mt-10 space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:p-6 shadow-soft">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    {status === 'completed' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        Completed
                      </span>
                    ) : status === 'failed' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                        Failed
                      </span>
                    ) : status === 'queued' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
                        Queued
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                        Running
                      </span>
                    )}
                    {docType && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold px-2.5 py-1">
                        {prettyDoc(docType)}
                      </span>
                    )}
                    {result && result.revised && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold px-2.5 py-1">
                        Revised after self-critique
                      </span>
                    )}
                  </div>
                  <h2 className="mt-3 font-bold text-xl text-slate-100">Agent execution log</h2>
                  <p className="text-sm text-slate-400 mt-1">
                    {status === 'completed'
                      ? 'All steps finished. Download the document below.'
                      : status === 'failed'
                      ? 'Generation stopped; see the error above.'
                      : 'Generating document and executing steps...'}
                  </p>
                </div>
              </div>

              {taskList && taskList.length > 0 && (
                <ol className="mt-5 space-y-2">
                  {taskList.map((t) => {
                    const [cls, icon] = statusBadge(t.status)
                    return (
                      <li
                        key={t.step}
                        className="flex items-center gap-3 rounded-xl border border-slate-800/50 bg-slate-950/50 px-4 py-2.5"
                      >
                        <span className="w-6 h-6 shrink-0 rounded-md bg-slate-900 border border-slate-700 text-xs font-bold text-slate-400 flex items-center justify-center">
                          {t.step}
                        </span>
                        <div className="flex-1 text-sm text-slate-300">{t.title}</div>
                        <span className={`inline-flex items-center gap-1 text-[11px] font-semibold rounded-full border px-2 py-0.5 ${cls}`}>
                          {icon} {t.status || 'pending'}
                        </span>
                      </li>
                    )
                  })}
                </ol>
              )}
            </div>

            {(assumptions.length > 0 || critique) && (
              <div className="grid md:grid-cols-2 gap-6">
                {assumptions.length > 0 && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center">
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="16" x2="12" y2="12" />
                          <line x1="12" y1="8" x2="12.01" y2="8" />
                        </svg>
                      </div>
                      <h3 className="font-bold text-slate-100">Assumptions the agent made</h3>
                    </div>
                    <ul className="space-y-1.5 text-sm text-slate-300">
                      {assumptions.map((a, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-amber-500 shrink-0">•</span>
                          <span>{a}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {critique && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${critique.needs_revision ? 'bg-indigo-500/10 text-indigo-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                      </div>
                      <h3 className="font-bold text-slate-100">Self-critique</h3>
                      <span className={`ml-auto text-[11px] font-semibold rounded-full border px-2 py-0.5 ${critique.needs_revision ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'}`}>
                        {critique.needs_revision ? 'Needs revision' : 'All good'}
                      </span>
                    </div>
                    {critique.issues && critique.issues.length > 0 ? (
                      <ul className="space-y-1.5 text-sm text-slate-300">
                        {critique.issues.map((i, idx) => (
                          <li key={idx} className="flex gap-2">
                            <span className="text-indigo-400 shrink-0">•</span>
                            <span>{i}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-slate-400">No issues found. The draft passed the quality gate.</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {result && (
              <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-900/50 p-6 shadow-soft">
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-wider text-brand-400">
                      Done · {prettyDoc(result.doc_type)}
                    </div>
                    <h3 className="mt-1 font-extrabold text-2xl text-slate-100">
                      {result.message}
                    </h3>
                    {result.revised && (
                      <p className="mt-2 text-sm text-slate-400 max-w-xl">
                        The draft was revised based on the agent's own critique to fix
                        gaps vs your original request.
                      </p>
                    )}
                  </div>
                  <a
                    href={downloadUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-100 hover:bg-white px-5 py-3 text-sm font-semibold text-slate-900 shadow-soft transition"
                  >
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download .docx
                  </a>
                </div>

                <dl className="mt-6 grid sm:grid-cols-3 gap-4 text-sm">
                  <div className="rounded-xl border border-slate-800/50 bg-slate-950/50 p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sections drafted</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-100">
                      {(result.task_list || []).filter((t) => String(t.title).startsWith('Draft section')).length}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-slate-800/50 bg-slate-950/50 p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Assumptions stated</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-100">{(result.assumptions || []).length}</dd>
                  </div>
                  <div className="rounded-xl border border-slate-800/50 bg-slate-950/50 p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total steps</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-100">{(result.task_list || []).length}</dd>
                  </div>
                </dl>
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="max-w-4xl mx-auto px-6 pb-12 flex flex-col items-center gap-4">
        <div className="text-sm text-slate-400 font-medium tracking-wide">
          Developed by Mohammed Thaher S
        </div>
        <div className="flex items-center gap-5">
          <a href="https://github.com/MohammedThaher01" target="_blank" rel="noreferrer" className="text-slate-500 hover:text-white transition-colors" aria-label="GitHub">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
            </svg>
          </a>
          <a href="https://www.linkedin.com/in/mohammed-thaher-s/" target="_blank" rel="noreferrer" className="text-slate-500 hover:text-[#0a66c2] transition-colors" aria-label="LinkedIn">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" clipRule="evenodd" />
            </svg>
          </a>
          <a href="mailto:thahercareer@gmail.com" className="text-slate-500 hover:text-rose-500 transition-colors" aria-label="Email">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
            </svg>
          </a>
        </div>
      </footer>
    </div>
  )
}
