import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { WorkspaceProvider } from './components/workspace'
import { Overview } from './pages/Overview'
import { Directory } from './pages/Directory'
import { Detail } from './pages/Detail'
import { Profile } from './pages/Profile'
import { Saved } from './pages/Saved'
import { Sources } from './pages/Sources'
import { ResearchAgent } from './pages/ResearchAgent'

export default function App() {
  return (
    <BrowserRouter>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <WorkspaceProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="opportunities" element={<Directory />} />
            <Route path="opportunities/:id" element={<Detail />} />
            <Route path="profile" element={<Profile />} />
            <Route path="saved" element={<Saved />} />
            <Route path="sources" element={<Sources />} />
            <Route path="research" element={<ResearchAgent />} />
            <Route
              path="*"
              element={
                <div className="page empty-state">
                  <h1>This page is off the map.</h1>
                  <p>Return to your workspace to keep exploring.</p>
                  <Link to="/" className="btn primary">
                    Back to overview
                  </Link>
                </div>
              }
            />
          </Route>
        </Routes>
      </WorkspaceProvider>
    </BrowserRouter>
  )
}
