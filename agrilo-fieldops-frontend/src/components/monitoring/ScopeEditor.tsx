import { useState } from 'react'
import { MapPin, Users } from 'lucide-react'
import { useFieldOps } from '../../state/useFieldOps'
import { visibleFarms } from '../../state/store'
import { syntheticFarms } from '../../demo/synthetic-farms'
import { demoFarmReferences, farmReference } from '../../features/monitoring/catalog'
import type { MonitorDefinition, MonitorScope } from '../../features/monitoring/types'
import { Field } from './MonitoringUi'
export function ScopeEditor({ value, onChange, saved }: { value: MonitorScope; onChange: (value: MonitorScope) => void; saved: MonitorDefinition[] }) {
  const home = useFieldOps(), [dataset, setDataset] = useState<'home' | 'demo'>(() => value.farms[0]?.source === 'home' ? 'home' : 'demo')
  const [scopeCandidates, setScopeCandidates] = useState(value.farms)
  const homeFarms = visibleFarms(home).map(f => farmReference(f, home.mode === 'mock' ? 'synthetic' : 'home'))
  const available = value.type !== 'specific' ? scopeCandidates : dataset === 'demo' ? syntheticFarms.map(f => farmReference(f)) : [...new Map([...value.farms, ...homeFarms].map(f => [f.id, f])).values()]
  const [search, setSearch] = useState('')
  const areas = saved.filter(m => m.input.scope.selection)
  const mode = (type: MonitorScope['type']) => {
    if (type === 'home_selection' && home.selection) { setDataset('home'); setScopeCandidates(homeFarms); onChange({ type, label: 'Home map area · snapshot', selection: home.selection, farms: homeFarms }); return }
    if (type === 'group') { setDataset('demo'); setScopeCandidates(demoFarmReferences); onChange({ type, groupId: 'demo-adama-cluster', label: 'Adama demonstration cluster', farms: demoFarmReferences }); return }
    if (type === 'saved_area' && areas[0]) { setScopeCandidates(areas[0].input.scope.farms); onChange({ ...areas[0].input.scope, type: 'saved_area' }); setDataset(areas[0].input.scope.farms[0]?.source === 'home' ? 'home' : 'demo'); return }
    onChange({ type, label: dataset === 'demo' ? 'Selected demonstration farms' : 'Selected Home farms', farms: [] })
  }
  return <div className="monitor-scope-editor">
    <div className="monitor-info"><MapPin size={17} /><p>Scope is saved as a snapshot. Future runs must revalidate farm access and geographic coverage.</p></div>
    <Field label="Target selection"><select aria-label="Target selection" value={value.type} onChange={e => mode(e.target.value as MonitorScope['type'])}>
      <option value="specific">Specific farms</option><option value="home_selection" disabled={!home.selection || !homeFarms.length}>Current Home map area{!homeFarms.length ? ' · open an area on Home first' : ''}</option>
      <option value="saved_area" disabled={!areas.length}>Previously saved geographic selection{!areas.length ? ' · none saved' : ''}</option><option value="group">Named demonstration farm group</option><option disabled>All assigned farms · authenticated service required</option>
    </select></Field>
    {value.type === 'saved_area' && <Field label="Saved area"><select aria-label="Saved area" onChange={e => { const selected = areas.find(m => m.id === e.target.value); if (selected) { setScopeCandidates(selected.input.scope.farms); onChange({ ...selected.input.scope, type: 'saved_area' }) } }} defaultValue={areas[0]?.id}>{areas.map(m => <option value={m.id} key={m.id}>{m.input.scope.label} · {m.input.name}</option>)}</select></Field>}
    {value.type === 'specific' && <div className="monitor-segment" aria-label="Farm data source"><button type="button" aria-pressed={dataset === 'demo'} onClick={() => { setDataset('demo'); onChange({ type: 'specific', label: 'Selected demonstration farms', farms: [] }) }}>Synthetic demo farms</button><button type="button" aria-pressed={dataset === 'home'} disabled={!homeFarms.length} onClick={() => { setDataset('home'); onChange({ type: 'specific', label: 'Selected Home farms', farms: homeFarms }) }}>Home context · {homeFarms.length}</button></div>}
    <Field label="Scope name"><input aria-label="Scope name" value={value.label} maxLength={120} onChange={e => onChange({ ...value, label: e.target.value })} /></Field>
    <div className="monitor-scope-summary"><Users size={17} /><strong>{value.farms.length} farms selected</strong><span>{value.farms.some(f => f.source === 'home') ? 'Home context' : 'Synthetic fixtures'}</span></div>
    <input className="monitor-farm-search" aria-label="Search target farms" placeholder="Find a farm or crop" value={search} onChange={e => setSearch(e.target.value)} />
    <div className="monitor-farm-list">
      {available.filter(f => (f.name + ' ' + f.crop).toLowerCase().includes(search.toLowerCase())).map(f => <label key={f.id}><input type="checkbox" checked={value.farms.some(v => v.id === f.id)} onChange={e => onChange({ ...value, farms: e.target.checked ? [...value.farms, f] : value.farms.filter(v => v.id !== f.id) })} /><span><strong>{f.name}</strong><small>{f.crop} · {f.source === 'synthetic' ? 'Synthetic' : 'Home context'}</small></span></label>)}
    </div>
    <div className="monitor-inline-actions"><button type="button" onClick={() => onChange({ ...value, farms: available })}>Select all listed farms</button><button type="button" onClick={() => onChange({ ...value, farms: [] })}>Clear farms</button>{home.selectedFarmId && homeFarms.some(f => f.id === home.selectedFarmId) && <button type="button" onClick={() => { setDataset('home'); onChange({ type: 'specific', label: 'Selected Home farm', farms: homeFarms.filter(f => f.id === home.selectedFarmId) }) }}>Use selected Home farm</button>}</div>
  </div>
}
