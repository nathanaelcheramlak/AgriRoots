import { useEffect, useState } from 'react'
import { Archive, ArrowUpRight, ChevronRight, FileText, History, Inbox, LayoutList, ListFilter, MessageSquareText, PanelLeftClose, Plus, Search, ShieldCheck, X } from 'lucide-react'
import { campaignTemplates, exampleSource, generateGuidance, newCampaignInput, outreachScenarios } from '../../features/outreach/catalog'
import type { CampaignInput, OutreachCampaign } from '../../features/outreach/types'
import { channelLabels, statusLabels } from '../../features/outreach/types'
import { mapFarmRecipients, syntheticRecipients } from '../../features/outreach/recipients'
import { campaignStatus, latestVersion } from '../../features/outreach/service'
import { outreachTransferStore, useOutreachTransfer } from '../../features/outreach/transfer'
import { useOutreach } from '../../features/outreach/store'
import { CampaignWizard } from './CampaignWizard'
import { CampaignDetail } from './CampaignDetail'
import { DeliveryHistory } from './DeliveryHistory'
import { FarmerResponses } from './FarmerResponses'
import { OutreachIcon, QuietState } from './OutreachUi'
function currentRoute() { return window.location.hash.replace(/^#outreach\/?/, '') }
export default function OutreachPage() {
  const state = useOutreach(), { pending } = useOutreachTransfer(), { load, notice, notify } = state
  const [route, setRoute] = useState(currentRoute), [search, setSearch] = useState(''), [filter, setFilter] = useState('all'), [sidebar, setSidebar] = useState(true), [drawer, setDrawer] = useState(false), [editing, setEditing] = useState<OutreachCampaign | null>(null)
  useEffect(() => { void load() }, [load])
  useEffect(() => { const change = () => { setRoute(currentRoute()); setDrawer(false); setEditing(null) }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => notify(null), 6000); return () => clearTimeout(timer) }, [notice, notify])
  useEffect(() => { const resize = () => { if (window.innerWidth > 1050) setDrawer(false) }; window.addEventListener('resize', resize); return () => window.removeEventListener('resize', resize) }, [])
  useEffect(() => {
    if (!drawer) return
    const previous = document.activeElement as HTMLElement | null, main = document.querySelector<HTMLElement>('.outreach-main')
    if (main) main.inert = true
    const controls = () => Array.from(document.querySelectorAll<HTMLElement>('.outreach-sidebar.is-open a,.outreach-sidebar.is-open button,.outreach-sidebar.is-open input')).filter(el => !el.hasAttribute('disabled') && el.getClientRects().length)
    controls()[0]?.focus()
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setDrawer(false); if (event.key === 'Tab') { const items = controls(), first = items[0], last = items.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() } } }
    document.addEventListener('keydown', key); return () => { document.removeEventListener('keydown', key); if (main) main.inert = false; if (previous?.isConnected) previous.focus() }
  }, [drawer])
  const create = (template: CampaignInput['templateId'] = 'custom', scenario?: string) => {
    const input = newCampaignInput(template)
    if (scenario === 'missing') { input.source = exampleSource('missing'); input.guidance = generateGuidance(template, input.source); input.selection.ids = ['DEMO-P0003'] }
    else if (scenario === 'large') input.selection.ids = syntheticRecipients.map(r => r.id)
    else if (scenario === 'constraints') input.selection.ids = syntheticRecipients.slice(0, 60).map(r => r.id)
    else if (scenario === 'weekly') input.selection.ids = ['DEMO-P0001', 'DEMO-P0005', 'DEMO-P0010']
    else if (scenario) input.selection.ids = mapFarmRecipients(input.source.farmIds, true).ids
    outreachTransferStore.setState({ pending: { id: crypto.randomUUID(), input, origin: scenario ? 'Synthetic scenario' : 'Outreach template', unmappedFarmIds: [] } }); window.location.hash = 'outreach/new'; setDrawer(false)
  }
  const show = (value: string) => { setFilter(value); window.location.hash = 'outreach'; setDrawer(false) }
  const campaigns = state.campaigns.filter(c => (!search || latestVersion(c).input.name.toLowerCase().includes(search.toLowerCase())) && (filter === 'all' || (filter === 'draft' ? campaignStatus(c) === 'draft' : c.archived)))
  const queue = state.campaigns.filter(c => ['awaiting_review', 'changes_requested'].includes(campaignStatus(c)))
  const pieces = route.split('/'), campaign = state.campaigns.find(c => c.id === pieces[0]), tab = pieces[1] ?? 'overview'
  const overview = !route, templatesOnly = route === 'templates'
  const saved = (c: OutreachCampaign) => { setEditing(null); outreachTransferStore.setState({ pending: null }); window.location.hash = 'outreach/' + c.id }
  return <div className="outreach-page plugins-theme">
    {drawer && <button className="outreach-sidebar-backdrop" aria-label="Close outreach sidebar" onClick={() => setDrawer(false)} />}
    <aside className={'outreach-sidebar ' + (!sidebar ? 'is-collapsed ' : '') + (drawer ? 'is-open' : '')} aria-label="Outreach navigation">
      <div className="outreach-sidebar-heading"><strong>Outreach</strong><button className="outreach-desktop-collapse" aria-label="Collapse outreach sidebar" onClick={() => setSidebar(false)}><PanelLeftClose size={17} /></button><button className="outreach-mobile-close" aria-label="Close outreach sidebar" onClick={() => setDrawer(false)}><X size={18} /></button></div>
      <button className="outreach-new-button" onClick={() => create()}><Plus size={17} />New Campaign</button>
      <label className="outreach-sidebar-search"><Search size={14} /><input aria-label="Search campaigns" placeholder="Search campaigns" value={search} onChange={e => { setSearch(e.target.value); window.location.hash = 'outreach' }} /></label>
      <nav aria-label="Outreach sections">
        <button className={overview && filter === 'all' ? 'selected' : ''} onClick={() => show('all')}><LayoutList size={16} />All Campaigns<span>{state.campaigns.length}</span></button>
        <button className={overview && filter === 'draft' ? 'selected' : ''} onClick={() => show('draft')}><FileText size={16} />Drafts</button>
        <a href="#outreach/review" className={route === 'review' ? 'selected' : ''}><ShieldCheck size={16} />Awaiting Review<span>{queue.length}</span></a>
        <a href="#outreach/delivery" className={route === 'delivery' ? 'selected' : ''}><History size={16} />Delivery History</a>
        <a href="#outreach/responses" className={route === 'responses' ? 'selected' : ''}><Inbox size={16} />Farmer Responses</a>
        <a href="#outreach/templates" className={templatesOnly ? 'selected' : ''}><MessageSquareText size={16} />Templates</a>
        <button className={overview && filter === 'archived' ? 'selected' : ''} onClick={() => show('archived')}><Archive size={16} />Archived</button>
      </nav>
      <div className="outreach-recent-title">Local campaign drafts</div><div className="outreach-recent-list">{!state.campaigns.length && <p>Your saved campaign drafts will appear here.</p>}{state.campaigns.slice().reverse().slice(0, 20).map(c => <a key={c.id} href={'#outreach/' + c.id} aria-current={pieces[0] === c.id ? 'page' : undefined}><OutreachIcon template={latestVersion(c).input.templateId} size={16} /><span><strong>{latestVersion(c).input.name}</strong><small>{statusLabels[campaignStatus(c)]}</small></span></a>)}</div>
      <footer><span />Preparation & local review only<small>No communication provider connected.</small></footer>
    </aside>
    <main className="outreach-main" aria-label="Outreach workspace"><div className="outreach-content">
      <header className="outreach-workspace-header"><div><button aria-label="Open outreach sidebar" onClick={() => { setSidebar(true); setDrawer(window.matchMedia('(max-width: 1050px)').matches) }}><ListFilter size={18} /></button><span>AGRILO <ChevronRight size={12} /> OUTREACH</span></div><span>Local prototype · no delivery</span></header>
      {state.warning && <div className="monitor-errors" role="status">{state.warning}</div>}{state.loading && <QuietState title="Reading local campaigns">Saved campaign drafts and their revision histories are loading.</QuietState>}
      {campaign && <CampaignDetail key={campaign.id + '-' + latestVersion(campaign).number} campaign={campaign} view={tab} onEdit={() => setEditing(campaign)} />}
      {(overview || templatesOnly) && !state.loading && <>
        <div className="outreach-page-heading"><div><span className="outreach-kicker">PREPARE. PERSONALIZE. REVIEW.</span><h1>{templatesOnly ? 'Campaign templates' : 'Outreach'}</h1><p>Turn agricultural insights into practical guidance for every farmer.</p></div><button className="monitor-primary" onClick={() => create()}><Plus size={16} />New Campaign</button></div>
        {overview && <>
          <div className="outreach-overview-stats">
            <div><span>Local draft campaigns</span><strong>{state.campaigns.filter(c => campaignStatus(c) === 'draft').length}</strong><small>Saved configurations</small></div>
            <div><span>Awaiting demo review</span><strong>{queue.length}</strong><small>Officer action needed</small></div>
            <div><span>Farmers in local drafts</span><strong>{new Set(state.campaigns.filter(c => !c.archived).flatMap(c => latestVersion(c).snapshot.memberIds)).size.toLocaleString()}</strong><small>Synthetic recipient IDs</small></div>
            <div><span>Demo reviews recorded</span><strong>{state.campaigns.filter(c => campaignStatus(c) === 'demo_reviewed').length}</strong><small>Not valid for delivery</small></div>
          </div>
          {!state.campaigns.length ? <section className="outreach-welcome"><span><MessageSquareText size={30} strokeWidth={1.5} /></span><div><h2>From insight to a thoughtful message.</h2><p>Choose the farmers, keep the evidence close, and review every proposed action before a future authorized delivery.</p><small>Local drafts only · SMS, voice, email and messaging are not configured</small></div></section> : <div className="outreach-campaign-list">{campaigns.map(c => { const v = latestVersion(c); return <a href={'#outreach/' + c.id} key={c.id}><span><OutreachIcon template={v.input.templateId} /></span><div><h2>{v.input.name}</h2><p>{v.snapshot.memberIds.length.toLocaleString()} selected · {v.snapshot.eligibleIds.length.toLocaleString()} eligible in demo · {channelLabels[v.input.communication.channel]}</p><small>Version {v.number} · {v.input.source.title}</small></div><em>{statusLabels[campaignStatus(c)]}</em><ArrowUpRight size={17} /></a> })}{!campaigns.length && <QuietState title="No matching campaigns">Try another search or filter.</QuietState>}</div>}
        </>}
        <section className="outreach-template-section"><div className="monitor-section-heading"><div><h2>{templatesOnly ? 'Choose a starting point' : 'Start with a purpose'}</h2><p>Source-aware templates for preparation, never automatic instructions or delivery.</p></div></div><div className="outreach-template-grid">{campaignTemplates.map(t => <button key={t.id} onClick={() => create(t.id)}><span><OutreachIcon template={t.id} /></span><div><h3>{t.name}</h3><p>{t.description}</p></div><Plus size={16} /></button>)}</div></section>
        <section className="outreach-scenarios"><h2>Explore synthetic workflows</h2><p>All counts come from the selected sample records. No real farmer contact information is included.</p><div>{outreachScenarios.map(s => <button key={s.id} onClick={() => create(s.template, s.id)}><strong>{s.name}<ArrowUpRight size={13} /></strong><span>{s.detail}</span></button>)}</div></section>
      </>}
      {route === 'review' && <section className="outreach-review-queue"><div className="outreach-page-heading"><div><h1>Review Queue</h1><p>Inspect exact versions, personalized groups, evidence and exclusions.</p></div><ShieldCheck size={24} /></div>{!queue.length ? <QuietState title="No local campaigns awaiting review">Submit a saved campaign for demo review. No authoritative approval or delivery integration is connected.</QuietState> : queue.map(c => { const v = latestVersion(c); return <article key={c.id}><div><span className="outreach-source-badge">{statusLabels[campaignStatus(c)]}</span><h2>{v.input.name}</h2><p>Version {v.number} · {v.snapshot.eligibleIds.length} eligible · {v.snapshot.excluded.length} excluded · {channelLabels[v.input.communication.channel]}</p><small>{v.input.source.title} · {v.input.source.evidence.length} evidence references · {v.input.guidance.corrections.length} officer corrections</small></div><a className="plugin-secondary" href={'#outreach/' + c.id + '/review'}>Open review<ArrowUpRight size={14} /></a></article> })}</section>}
      {route === 'delivery' && <DeliveryHistory />}{route === 'responses' && state.loaded && <FarmerResponses />}
      {route && !campaign && !['new', 'templates', 'review', 'delivery', 'responses'].includes(route) && !state.loading && <QuietState title="Campaign not found">This local campaign may have been deleted or belongs to another browser. <a href="#outreach">Return to Outreach.</a></QuietState>}
      <footer className="outreach-page-footer"><span>Human control, at every step.</span>Evidence, precise scope, clear review boundaries.</footer>
    </div></main>
    {(route === 'new' || editing) && <CampaignWizard key={editing?.id ?? pending?.id ?? 'new'} existing={editing ?? undefined} initial={pending?.input} origin={editing ? undefined : pending?.origin} unmapped={editing ? undefined : pending?.unmappedFarmIds} onClose={() => { if (editing) setEditing(null); else { outreachTransferStore.setState({ pending: null }); window.location.hash = 'outreach' } }} onSaved={saved} />}
    {notice && <div className="plugin-toast" role="status"><span>{notice}</span><button aria-label="Dismiss outreach notification" onClick={() => notify(null)}><X size={16} /></button></div>}
  </div>
}
