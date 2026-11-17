import { lazy, Suspense, useEffect, useState } from 'react'
import { BookOpen, House, Menu, MessageSquareText, Radar, Sprout, X } from 'lucide-react'
import HomeWorkspace from './HomeWorkspace'
import PluginsPage from '../components/plugins/PluginsPage'
import { PluginSocketIcon } from '../components/plugins/PluginIcon'
const SkillsPage = lazy(() => import('../components/skills/SkillsPage'))
const MonitoringPage = lazy(() => import('../components/monitoring/MonitoringPage'))
const OutreachPage = lazy(() => import('../components/outreach/OutreachPage'))

function currentPage(): 'home' | 'plugins' | 'skills' | 'monitoring' | 'outreach' { return window.location.hash === '#skills' ? 'skills' : window.location.hash.startsWith('#outreach') ? 'outreach' : window.location.hash.startsWith('#monitoring') ? 'monitoring' : window.location.hash === '#plugins' ? 'plugins' : 'home' }
export default function App() {
  const [page, setPage] = useState(currentPage), [navigationOpen, setNavigationOpen] = useState(false)
  const [homeMounted, setHomeMounted] = useState(() => currentPage() === 'home')
  useEffect(() => { const update = () => { const next = currentPage(); setPage(next); if (next === 'home') setHomeMounted(true); setNavigationOpen(false) }; window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update) }, [])
  useEffect(() => {
    if (!navigationOpen) return
    const previous = document.activeElement as HTMLElement | null
    const controls = () => Array.from(document.querySelectorAll<HTMLElement>('.global-rail.is-open a,.global-rail.is-open button:not(:disabled)'))
    controls()[0]?.focus()
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNavigationOpen(false)
      if (event.key === 'Tab') { const items = controls(), first = items[0], last = items.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() } }
    }
    window.addEventListener('keydown', escape); return () => { window.removeEventListener('keydown', escape); if (previous?.isConnected) previous.focus() }
  }, [navigationOpen])
  return <div className="app-shell">
    <header className="shell-mobile-header"><button aria-label="Open navigation" aria-expanded={navigationOpen} onClick={() => setNavigationOpen(true)}><Menu size={21} /></button><span>AgriLo <strong>{page === 'home' ? 'FieldOps' : page === 'plugins' ? 'Customize' : page === 'skills' ? 'Skills' : page === 'outreach' ? 'Outreach' : 'Monitoring'}</strong></span>{page === 'outreach' ? <MessageSquareText size={20} /> : page === 'monitoring' ? <Radar size={20} /> : <PluginSocketIcon size={20} />}</header>
    {navigationOpen && <button className="shell-nav-backdrop" aria-label="Close navigation" onClick={() => setNavigationOpen(false)} />}
    <nav className={`global-rail ${navigationOpen ? 'is-open' : ''}`} aria-label="Application navigation">
      <div className="rail-brand"><Sprout size={24} /><span>AgriLo</span><button aria-label="Close navigation" onClick={() => setNavigationOpen(false)}><X size={20} /></button></div>
      <div className="global-rail-links"><a href="#home" aria-label="Home" aria-current={page === 'home' ? 'page' : undefined} title="Home" onClick={() => setNavigationOpen(false)}><House size={21} /><span>Home</span></a><a href="#plugins" aria-label="Plugins" aria-current={page === 'plugins' ? 'page' : undefined} title="Plugins" onClick={() => setNavigationOpen(false)}><PluginSocketIcon /><span>Plugins</span></a><a href="#skills" aria-label="Skills" aria-current={page === 'skills' ? 'page' : undefined} title="Skills" onClick={() => setNavigationOpen(false)}><BookOpen size={21} /><span>Skills</span></a><span className="rail-separator" /><a href="#monitoring" aria-label="Monitoring" aria-current={page === 'monitoring' ? 'page' : undefined} title="Monitoring" onClick={() => setNavigationOpen(false)}><Radar size={21} /><span>Monitoring</span></a><a href="#outreach" aria-label="Outreach" aria-current={page === 'outreach' ? 'page' : undefined} title="Outreach" onClick={() => setNavigationOpen(false)}><MessageSquareText size={21} /><span>Outreach</span></a></div>
      <div className="rail-account" title={import.meta.env.VITE_API_MODE === 'http' ? 'Backend Home, Plugins and Skills · Monitoring and Outreach remain local drafts' : 'Local demo officer'}><span>{import.meta.env.VITE_API_MODE === 'http' ? 'FO' : 'DO'}</span><div>{import.meta.env.VITE_API_MODE === 'http' ? 'Officer workspace' : 'Demo officer'}<small>{import.meta.env.VITE_API_MODE === 'http' ? 'Home, Plugins and Skills' : 'Local workspace'}</small></div></div>
    </nav>
    <div className="app-page-stack" inert={navigationOpen}><div className="home-surface" hidden={page !== 'home'} inert={page !== 'home'}>{homeMounted && <HomeWorkspace active={page === 'home'} />}</div>{page === 'plugins' && <div className="plugins-surface"><PluginsPage /></div>}{page === 'skills' && <div className="plugins-surface"><Suspense fallback={<div role="status">Opening Skills…</div>}><SkillsPage /></Suspense></div>}{page === 'monitoring' && <div className="monitoring-surface"><Suspense fallback={<div className="monitor-opening" role="status">Opening Monitoring…</div>}><MonitoringPage /></Suspense></div>}{page === 'outreach' && <div className="outreach-surface"><Suspense fallback={<div className="monitor-opening" role="status">Opening Outreach…</div>}><OutreachPage /></Suspense></div>}</div>
  </div>
}
