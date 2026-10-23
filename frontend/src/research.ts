import { useEffect, useState } from 'react'
import { api } from './api'

export interface ResearchPlan {
  questions: { id: string; question: string; fields: string[]; completion_criterion: string }[]
  constraints: string[]
  search_tasks: string[]
  completion_criteria: string[]
}
export interface ResearchRun {
  id: string
  objective: string
  mode: 'demo' | 'live'
  status: string
  outcome: string | null
  error: string | null
  stop_reason: string | null
  cancel_requested: boolean
  stats: Record<string, number>
  state: { phase?: string }
  created_at: string
  request: { limits: Record<string, number>; demo_scenario: string; allowed_domains: string[] }
  plans: { revision: number; content: ResearchPlan; created_at: string }[]
  steps: {
    id: string
    node: string
    sequence: number
    summary: string
    created_at: string
    data: Record<string, unknown>
  }[]
}
export interface ResearchSnippet {
  id: string
  document_id: string
  quote: string
  start: number
  end: number
  location: { page?: number }
  purpose: string
  url: string
  source_hash: string
  synthetic: boolean
}
export interface ResearchClaim {
  id: string
  field: string
  value: string
  state: string
  scope: {
    program: string
    intake_year: number | null
    award_track?: string | null
    applicant_group?: string | null
    source_version?: string | null
  }
  evidence_id: string | null
  scope_evidence_id: string | null
  verification_note: string
  semantic_assessment?: SupportAssessment
}
export interface SupportAssessment {
  label?: string
  method?: string
  reason?: string
  resolution?: string
  passage?: string
}
export interface QuestionAssessment {
  question_id: string
  question: string
  status: string
  scope: ResearchClaim['scope'] | null
  fields: { field: string; status: string; resolution: string }[]
}
export interface ResearchDocument {
  id: string
  url: string
  title: string
  sha256: string
  media_type: string
  synthetic: boolean
  fetched_at: string
  last_checked_at: string
}
export interface ResearchEvidence {
  claims: ResearchClaim[]
  snippets: ResearchSnippet[]
  documents: ResearchDocument[]
  sources: {
    id: string
    url: string
    document_id: string | null
    status: string
    cache_hit: boolean
    message: string
  }[]
  unknowns: { field: string; reason: string; scope: ResearchClaim['scope'] | null }[]
  contradictions: { id: string; field: string; summary: string; claim_ids: string[] }[]
}
export interface ResearchReport {
  executive_summary: string
  outcome: string
  synthetic: boolean
  investigated_opportunities: ResearchClaim['scope'][]
  findings: {
    claim_id: string
    field: string
    value: string
    state: string
    evidence_id: string
    scope_evidence_id: string
    scope: ResearchClaim['scope']
  }[]
  unanswered_questions: ResearchEvidence['unknowns']
  recommended_next_investigations: string[]
  limitations: string[]
  question_assessments?: QuestionAssessment[]
  context_differences?: { field: string; relation: string; resolution: string }[]
  temporal_warnings?: { claim_id: string; value: string; warning: string; as_of_date: string }[]
  run_metadata: {
    stop_reason: string
    stats: Record<string, number>
    llm_driven: boolean
    plan_revisions: number
  }
}
export interface Capabilities {
  live_ready: boolean
  model: string | null
  search_configured: boolean
  model_notice: string
  demo_notice: string
  execution: string
}
export const DEMO_OBJECTIVE =
  "Investigate the synthetic Lumen AI Master's 2027 tuition and living funding, deadline, and proof-of-funds requirements. This is an offline fixture demo."
export const researchLabels: Record<string, string> = {
  institution: 'Institution',
  program: 'Program',
  degree: 'Degree',
  intake_year: 'Intake year',
  deadline: 'Application deadline',
  tuition_funding: 'Tuition funding',
  living_stipend: 'Living expenses',
  eligibility: 'Eligibility',
  language: 'Language requirements',
  application_fee: 'Application fee',
  proof_of_funds: 'Proof of funds',
  scholarship_obligations: 'Scholarship obligations',
}
export const terminal = (status: string) => !['pending', 'running'].includes(status)

export function useResearchRun(id: string, finished: () => void) {
  const [snapshot, setSnapshot] = useState<{
    run?: ResearchRun
    evidence?: ResearchEvidence
    report?: ResearchReport
    error?: string
  }>({})
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let signature = ''
    let evidence: ResearchEvidence | undefined
    const controller = new AbortController()
    async function poll() {
      try {
        const run = await api<ResearchRun>(`/research/runs/${id}`, { signal: controller.signal })
        const nextSignature = `${run.steps.length}:${run.status}`
        if (signature !== nextSignature) {
          evidence = await api<ResearchEvidence>(`/research/runs/${id}/evidence`, {
            signal: controller.signal,
          })
          signature = nextSignature
        }
        const report = terminal(run.status)
          ? await api<ResearchReport>(`/research/runs/${id}/report`, { signal: controller.signal })
          : undefined
        if (!active) return
        setSnapshot({ run, evidence, report })
        if (terminal(run.status)) finished()
        else timer = setTimeout(poll, 1000)
      } catch (error) {
        if (active && !controller.signal.aborted)
          setSnapshot((s) => ({ ...s, error: (error as Error).message }))
      }
    }
    void poll()
    return () => {
      active = false
      controller.abort()
      clearTimeout(timer)
    }
  }, [id, finished])
  return snapshot
}
