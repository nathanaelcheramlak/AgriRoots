import { CloudSun, Database, Droplets, Globe2, Leaf, Radio, Satellite, ShieldPlus, Sprout, Truck, Waves } from 'lucide-react'
import type { PluginCategory } from '../../features/plugins/types'

// Original AgriLo socket mark: a circular port with three linked contacts.
export function PluginSocketIcon({ size = 22 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.5" /><path d="M12 5.8v4.1m5.35 5.2-3.5-2.05m-7.2 2.05 3.5-2.05" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><path d="M12 9.9a2.1 2.1 0 0 1 1.85 3.15m-3.7 0a2.1 2.1 0 0 1 0-2.1m3.7 2.1a2.1 2.1 0 0 1-3.7 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
}
const categoryIcons = { weather: CloudSun, soil: Sprout, satellite: Satellite, diagnosis: ShieldPlus, pests: Leaf, markets: Truck, field_operations: Radio, custom: Globe2 }
const specialIcons = { nasa_power: Globe2, nasa_power_mcp: Globe2, chirps: Droplets, fao_wapor: Waves, fao_fpma: Database }
export function ProviderIcon({ id, category }: { id: string; category: PluginCategory }) {
  const Icon = specialIcons[id as keyof typeof specialIcons] ?? categoryIcons[category]
  return <span className={`provider-icon provider-${category}`}><Icon size={23} strokeWidth={1.7} /></span>
}
