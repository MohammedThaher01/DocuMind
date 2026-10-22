import { useState } from 'react'

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
    done:   ['bg-emerald-100 text-emerald-700 border-emerald-200', '✓'],
    pending:['bg-slate-100 text-slate-500 border-slate-200', ''],
    running:['bg-amber-100 text-amber-700 border-amber-200', '…'],
    failed: ['bg-rose-100 text-rose-700 border-rose-200', '✕'],
  }
  return map[status] || map.pending
}

export default function App() {
  const [request, setRequest] = useState(SAMPLE_PROMPTS[0].prompt)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const [status, setStatus] = useState(null) // queued | running | completed | failed
  const [taskList, setTaskList] = useState([])
  const [assumptions, setAssumptions] = useState([])
  const [docType, setDocType] = useState('')
  const [critique, setCritique] = useState(null)
  const [result, setResult] = useState(null) // final AgentResponse

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

        setResult(data)
        setTaskList(data.task_list || [])
        setAssumptions(data.assumptions || [])
        setDocType(data.doc_type || '')
        setCritique(data.critique || null)
        setStatus('completed')

        if (data.download_url) {
          const link = document.createElement('a')
          link.href = data.download_url
          const filename = data.download_url.split('/').pop() || 'generated_document.docx'
          link.setAttribute('download', filename)
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
        }
        
      } catch (err) {
        setStatus('failed')
        setError(err.message || String(err))
      } finally {
        setSubmitting(false)
      }
    }

    const downloadUrl = result?.download_url || ''
    const active = submitting || Boolean(result)
    const charCount = request.length

  return (
    <div className="min-h-screen w-full">
      {/* Nav */}
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
            <div className="font-extrabold text-lg tracking-tight text-slate-900">DocuMind</div>
            <div className="text-xs text-slate-500 -mt-0.5">Autonomous Document Agent</div>
          </div>
        </div>
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="hidden sm:inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 transition"
        >
          API Docs
          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 17L17 7" /><path d="M7 7h10v10" />
          </svg>
        </a>
      </header>

      {/* Hero + input */}
      <main className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 text-brand-700 text-xs font-semibold px-3 py-1 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            LangGraph · Groq · Self-reflecting agent
          </div>
          <h1 className="font-extrabold text-4xl sm:text-5xl tracking-tight text-slate-900 leading-[1.05]">
            Describe it. DocuMind{' '}
            <span className="bg-gradient-to-r from-brand-600 to-indigo-500 bg-clip-text text-transparent">
              plans, writes, critiques, and ships
            </span>{' '}
            the document.
          </h1>
          <p className="mt-5 text-slate-600 max-w-2xl mx-auto leading-relaxed">
            Turn a plain-English business request into a polished Word document.
            The agent classifies the document type, fills in gaps with stated
            assumptions, drafts section-by-section, self-critiques, revises,
            and exports a .docx — all autonomously.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-10">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-soft p-5 sm:p-6">
            <label htmlFor="request" className="block text-sm font-semibold text-slate-800 mb-2">
              What document do you need?
            </label>
            <textarea
              id="request"
              rows={5}
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="e.g. Create a product spec for an AI-powered mobile expense tracker…"
              className="block w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder-slate-400 text-[15px] leading-relaxed outline-none ring-brand-500/20 focus:bg-white focus:border-brand-400 focus:ring-4 transition"
              maxLength={4000}
              disabled={submitting}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-slate-500">
                <span className={charCount > 3800 ? 'text-amber-600 font-medium' : ''}>{charCount}</span>
                <span className="opacity-60"> / 4000 chars</span>
              </div>
              <button
                type="submit"
                disabled={submitting || !request.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-brand-600 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-soft hover:from-brand-700 hover:to-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
              >
                {submitting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                    Generating…
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
                  className="rounded-full border border-slate-200 bg-white text-sm px-3.5 py-1.5 text-slate-700 hover:border-brand-300 hover:text-brand-700 hover:bg-brand-50 disabled:opacity-60 transition"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </form>

        {/* Error */}
        {error && (
          <div className="mt-8 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 flex items-start gap-3">
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

        {/* Progress + results */}
        {active && (
          <section className="mt-10 space-y-6">
            {/* Status header */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-soft">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    {status === 'completed' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 border border-emerald-200 text-emerald-700 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Completed
                      </span>
                    ) : status === 'failed' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 border border-rose-200 text-rose-700 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                        Failed
                      </span>
                    ) : status === 'queued' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
                        Queued
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 border border-amber-200 text-amber-700 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                        Running
                      </span>
                    )}
                    {docType && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-semibold px-2.5 py-1">
                        {prettyDoc(docType)}
                      </span>
                    )}
                    {result && result.revised && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold px-2.5 py-1">
                        Revised after self-critique
                      </span>
                    )}
                    {result && result.review_required && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 border border-rose-200 text-rose-700 text-xs font-semibold px-2.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                        Needs human review
                      </span>
                    )}
                  </div>
                  <h2 className="mt-3 font-bold text-xl text-slate-900">Agent execution log</h2>
                  <p className="text-sm text-slate-600 mt-1">
                    {status === 'completed'
                      ? 'All steps finished. Download the document below.'
                      : status === 'failed'
                      ? 'Generation stopped — see the error above.'
                      : 'The agent is processing your request. Results appear when generation finishes.'}
                  </p>
                </div>

              </div>

              {/* Task list */}
              {taskList && taskList.length > 0 && (
                <ol className="mt-5 space-y-2">
                  {taskList.map((t) => {
                    const [cls, icon] = statusBadge(t.status)
                    return (
                      <li
                        key={t.step}
                        className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/60 px-4 py-2.5"
                      >
                        <span className="w-6 h-6 shrink-0 rounded-md bg-white border border-slate-200 text-xs font-bold text-slate-500 flex items-center justify-center">
                          {t.step}
                        </span>
                        <div className="flex-1 text-sm text-slate-800">{t.title}</div>
                        <span className={`inline-flex items-center gap-1 text-[11px] font-semibold rounded-full border px-2 py-0.5 ${cls}`}>
                          {icon} {t.status || 'pending'}
                        </span>
                      </li>
                    )
                  })}
                </ol>
              )}
            </div>

            {/* Assumptions + Critique */}
            {(assumptions.length > 0 || critique) && (
              <div className="grid md:grid-cols-2 gap-6">
                {assumptions.length > 0 && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="16" x2="12" y2="12" />
                          <line x1="12" y1="8" x2="12.01" y2="8" />
                        </svg>
                      </div>
                      <h3 className="font-bold text-slate-900">Assumptions the agent made</h3>
                    </div>
                    <ul className="space-y-1.5 text-sm text-slate-700">
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
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${critique.needs_revision ? 'bg-indigo-100 text-indigo-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                      </div>
                      <h3 className="font-bold text-slate-900">Self-critique</h3>
                      <span className={`ml-auto text-[11px] font-semibold rounded-full border px-2 py-0.5 ${critique.needs_revision ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}>
                        {critique.needs_revision ? 'Needs revision' : 'All good'}
                      </span>
                    </div>
                    {critique.issues && critique.issues.length > 0 ? (
                      <ul className="space-y-1.5 text-sm text-slate-700">
                        {critique.issues.map((issue, idx) => {
                          const claim = typeof issue === 'string'
                            ? issue
                            : (issue?.claim || issue?.explanation || 'Unspecified validation issue')
                          const severity = typeof issue === 'object' && issue ? issue.severity : null
                          return (
                            <li key={idx} className="flex gap-2">
                              <span className="text-indigo-500 shrink-0">•</span>
                              <span>
                                {severity && <strong className="mr-1 uppercase text-[11px]">[{severity}]</strong>}
                                {claim}
                              </span>
                            </li>
                          )
                        })}
                      </ul>
                    ) : (
                      <p className="text-sm text-slate-600">No issues found — draft passed the quality gate.</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Final result card */}
            {result && (
              <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-brand-50/40 p-6 shadow-soft">
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-wider text-brand-700">
                      Done · {prettyDoc(result.doc_type)}
                    </div>
                    <h3 className="mt-1 font-extrabold text-2xl text-slate-900">
                      {result.message}
                    </h3>
                    {result.revised && (
                      <p className="mt-2 text-sm text-slate-600 max-w-xl">
                        The draft was revised based on the agent's own critique to fix
                        gaps vs your original request.
                      </p>
                    )}
                  </div>
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 hover:bg-slate-800 px-5 py-3 text-sm font-semibold text-white shadow-soft transition"
                  >
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download .docx
                  </a>
                </div>

                {result.review_required && (
                  <div className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4">
                    <div className="flex items-start gap-3">
                      <svg viewBox="0 0 24 24" className="w-5 h-5 mt-0.5 shrink-0 text-rose-600" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      <div className="min-w-0">
                        <div className="font-semibold text-rose-800">
                          Not validated — human review required
                        </div>
                        <p className="mt-0.5 text-sm text-rose-700">
                          Material issues remained after {result.revision_count ?? 0} revision pass
                          {(result.revision_count ?? 0) === 1 ? '' : 'es'}. Treat this document as a draft and
                          resolve the following before relying on it.
                        </p>
                        {result.unresolved_issues && result.unresolved_issues.length > 0 && (
                          <ul className="mt-3 space-y-1.5 text-sm text-rose-800">
                            {result.unresolved_issues.map((issue, idx) => (
                              <li key={idx} className="flex gap-2">
                                <span className="shrink-0 font-semibold uppercase text-[11px] mt-0.5 rounded border border-rose-300 bg-white px-1.5 py-0.5">
                                  {issue.severity || 'issue'}
                                </span>
                                <span>{issue.claim}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <dl className="mt-6 grid sm:grid-cols-3 gap-4 text-sm">
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sections drafted</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-900">
                      {(result.task_list || []).filter((t) => String(t.title).startsWith('Draft section')).length}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Assumptions stated</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-900">{(result.assumptions || []).length}</dd>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total steps</dt>
                    <dd className="mt-1 font-bold text-xl text-slate-900">{(result.task_list || []).length}</dd>
                  </div>
                </dl>


              </div>
            )}
          </section>
        )}
      </main>

      <footer className="max-w-4xl mx-auto px-6 pb-10 text-center text-xs text-slate-500">
        Powered by FastAPI · LangGraph · Groq · python-docx · Vite · Tailwind CSS
      </footer>
    </div>
  )
}
