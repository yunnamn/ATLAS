export type FactState = 'unknown' | 'unverified' | 'verified'
export interface Fact {
  value: string | null
  state: FactState
  source_id: string | null
  excerpt: string | null
}
export interface Source {
  id: string
  label: string
  kind: 'demo' | 'official_url' | 'document' | 'manual'
  url: string | null
  retrieved_at: string | null
  content_sha256: string | null
  official_asserted: boolean
}
export interface Opportunity {
  id: number
  external_id: string
  title: string
  institution: string
  country: string
  category: string
  summary: string
  subjects: string[]
  synthetic: boolean
  sources: Source[]
  facts: Record<string, Fact>
  revision: number
  created_at: string
  updated_at: string
}
export interface Directory {
  items: Opportunity[]
  total: number
  total_all: number
  countries: string[]
}
export interface Application {
  id: number
  opportunity_id: number
  status: string
  notes: string
  missing_requirements: string[]
  updated_at: string
  opportunity: Opportunity
}
export interface Profile {
  name: string
  nationality: string | null
  education: 'bachelor' | 'master' | 'other' | null
  gpa: number | null
  ielts: number | null
  interests: string[]
  preferred_countries: string[]
  requires_full_funding: boolean
}
export interface Match {
  score: number | null
  label: string
  eligibility: string
  checks: { kind: string; label: string; outcome: string; detail: string }[]
  warnings: string[]
  disclaimer: string
}
export interface History {
  id: number
  revision: number
  actor: string
  reason: string
  before: Opportunity | null
  after: Opportunity
  created_at: string
}
