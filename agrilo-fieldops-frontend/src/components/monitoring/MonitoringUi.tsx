import { Activity, CloudSun, FileText, Leaf, Radar, Satellite } from 'lucide-react'
import type { MonitorInput } from '../../features/monitoring/types'
export function MonitorSymbol({ template = 'custom', size = 22 }: { template?: MonitorInput['templateId']; size?: number }) {
  const Icon = ({ weather: CloudSun, report: FileText, photos: Leaf, satellite: Satellite, custom: Radar })[template]
  return <Icon size={size} strokeWidth={1.6} />
}
export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <label className="monitor-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}
export function SampleNotice({ children }: { children?: React.ReactNode }) {
  return <div className="monitor-sample-notice"><Activity size={16} /><p><strong>Synthetic demonstration</strong>{children ?? 'Fixed sample records. No monitoring job, provider call or crop diagnosis has taken place.'}</p></div>
}
export function QuietState({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="monitor-quiet-state"><Radar size={27} strokeWidth={1.4} /><h3>{title}</h3><p>{children}</p></div>
}
export function formatDate(value: string) { return new Date(value).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Africa/Addis_Ababa' }) + ' EAT' }
