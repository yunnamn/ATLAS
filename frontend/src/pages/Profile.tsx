import { Check, LockKeyhole, Save, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { api, useResource } from '../api'
import { ErrorBox, Loading } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Profile as ProfileData } from '../types'

function ProfileForm({ initial }: { initial: ProfileData }) {
  const [profile, setProfile] = useState(initial)
  const [interests, setInterests] = useState(initial.interests.join(', '))
  const [countries, setCountries] = useState(initial.preferred_countries.join(', '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { refresh, notify } = useWorkspace()
  function update<K extends keyof ProfileData>(key: K, value: ProfileData[K]) {
    setProfile((p) => ({ ...p, [key]: value }))
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('/profile', {
        method: 'PUT',
        body: JSON.stringify({
          ...profile,
          interests: interests
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
          preferred_countries: countries
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      })
      refresh()
      notify('Profile saved. Compatibility explanations now use these preferences.')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="profile-grid">
      <div>
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">YOUR BACKGROUND</div>
              <h2>A foundation for better research</h2>
            </div>
            <Settings2 size={21} />
          </div>
          <p className="muted">
            Only add what you’re comfortable storing locally. Blank values remain unknown in
            requirement checks.
          </p>
          <div className="form-grid">
            <label>
              Display name
              <input
                value={profile.name}
                required
                maxLength={100}
                onChange={(e) => update('name', e.target.value)}
              />
            </label>
            <label>
              Nationality (two-letter ISO code)
              <input
                value={profile.nationality ?? ''}
                placeholder="e.g. UZ"
                pattern="[A-Z]{2}"
                maxLength={2}
                onChange={(e) => update('nationality', e.target.value.toUpperCase() || null)}
              />
            </label>
            <label>
              Highest completed education
              <select
                value={profile.education ?? ''}
                onChange={(e) =>
                  update('education', (e.target.value || null) as ProfileData['education'])
                }
              >
                <option value="">Not recorded</option>
                <option value="bachelor">Bachelor’s degree</option>
                <option value="master">Master’s degree</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              GPA on a 4.0 scale
              <input
                type="number"
                step="0.01"
                min="0"
                max="4"
                value={profile.gpa ?? ''}
                onChange={(e) => update('gpa', e.target.value ? Number(e.target.value) : null)}
                placeholder="Not recorded"
              />
            </label>
            <label>
              IELTS overall score
              <input
                type="number"
                step="0.5"
                min="0"
                max="9"
                value={profile.ielts ?? ''}
                onChange={(e) => update('ielts', e.target.value ? Number(e.target.value) : null)}
                placeholder="Not recorded"
              />
            </label>
          </div>
          <p className="field-note">
            No automatic GPA conversions are made. The current evaluator supports IELTS only;
            equivalent tests need individual review.
          </p>
        </section>
        <section className="panel">
          <div className="eyebrow">WHAT MATTERS TO YOU</div>
          <h2>Interests & priorities</h2>
          <div className="form-grid one-column">
            <label>
              Subject interests (comma-separated)
              <input
                value={interests}
                maxLength={1600}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="Artificial intelligence, Research"
              />
              <small>
                Exact subject tags, ignoring case. Try Artificial intelligence or Computer science.
              </small>
            </label>
            <label>
              Preferred destinations (comma-separated)
              <input
                value={countries}
                maxLength={2400}
                onChange={(e) => setCountries(e.target.value)}
                placeholder="Germany, Sweden, Japan"
              />
            </label>
            <label className="checkbox-panel">
              <input
                type="checkbox"
                checked={profile.requires_full_funding}
                onChange={(e) => update('requires_full_funding', e.target.checked)}
              />
              <span>
                <strong>I need tuition and living support</strong>
                <small>
                  This checks the funding claim. Travel, insurance, and other costs still need
                  review.
                </small>
              </span>
            </label>
          </div>
        </section>
        {error && <ErrorBox error={error} />}
        <button className="btn primary" disabled={busy}>
          <Save size={16} />
          {busy ? 'Saving…' : 'Save profile & preferences'}
        </button>
      </div>
      <aside>
        <section className="panel profile-explainer">
          <span className="stat-icon">
            <LockKeyhole size={23} />
          </span>
          <h2>
            Your profile.
            <br />
            Your perspective.
          </h2>
          <p>ATLAS uses transparent rules. It doesn’t predict your admissions chances.</p>
          <ol>
            <li>
              <strong>Eligibility requirements</strong>
              <p>
                Nationality, degree, GPA, and IELTS are checked separately. Unverified rules stay
                provisional.
              </p>
            </li>
            <li>
              <strong>Preference fit</strong>
              <p>
                Destination (35), subjects (35), and funding (30). Only enabled preferences enter
                the denominator.
              </p>
            </li>
            <li>
              <strong>Uncertainty stays visible</strong>
              <p>
                Unknown funding earns no funding points. Gaps and unknown requirements never count
                as a pass.
              </p>
            </li>
          </ol>
          <div className="privacy-note">
            <Check size={15} />
            Stored in your local database. No model API calls.
          </div>
        </section>
      </aside>
    </form>
  )
}
export function Profile() {
  const { data, error, loading } = useResource<ProfileData>('/profile')
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">A MORE PERSONAL PERSPECTIVE</div>
          <h1>Your direction, defined.</h1>
          <p>Give your research context. Keep every recommendation explainable.</p>
        </div>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} />
      ) : (
        data && <ProfileForm initial={data} />
      )}
    </div>
  )
}
