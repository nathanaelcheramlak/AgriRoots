import { AlertTriangle, CircleHelp, ShieldCheck } from 'lucide-react'
import type { Farm } from '../api/types'
import { titleCase } from '../lib/format'
export function RiskBadge({ risk }: { risk: Farm['riskLevel'] }) { return <span className={`risk-badge ${risk}`}>{risk === 'high' ? <AlertTriangle size={12} /> : risk === 'unknown' ? <CircleHelp size={12} /> : <ShieldCheck size={12} />}{titleCase(risk)} priority</span> }
export function EmptyState({ title, text, children }: { title: string; text: string; children?: React.ReactNode }) { return <div className="empty-state"><div className="empty-icon"><CircleHelp size={24} /></div><h3>{title}</h3><p>{text}</p>{children}</div> }
