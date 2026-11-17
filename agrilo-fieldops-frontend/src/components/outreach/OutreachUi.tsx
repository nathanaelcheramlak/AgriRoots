import { CalendarDays, CloudRain, Droplets, Leaf, MapPin, MessageSquareText, PenLine, ShieldCheck } from 'lucide-react'
import type { CampaignInput } from '../../features/outreach/types'
export { Field, formatDate, QuietState } from '../monitoring/MonitoringUi'
export function OutreachIcon({ template = 'custom', size = 22 }: { template?: CampaignInput['templateId']; size?: number }) {
  const Icon = ({ weekly: CalendarDays, weather: CloudRain, health: Leaf, irrigation: Droplets, inspection: MapPin, custom: PenLine })[template]
  return <Icon size={size} strokeWidth={1.6} />
}
export function LocalNotice({ children }: { children?: React.ReactNode }) {
  return <div className="outreach-local-notice"><ShieldCheck size={18} /><p><strong>Local preparation · no delivery</strong>{children ?? 'Drafts and demo decisions stay on this device. No message, email or call will be sent.'}</p></div>
}
export function SyntheticNotice() { return <div className="outreach-synthetic-notice"><MessageSquareText size={17} /><p><strong>Synthetic demonstration</strong>Fixed example records, without real farmer contacts, provider activity or deliveries.</p></div> }
