import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export function PluginModal({ title, children, onClose, wide = false }: { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLElement>(null), closeRef = useRef(onClose), id = useId()
  closeRef.current = onClose
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null, shell = document.querySelector<HTMLElement>('.app-shell')
    const priorInert = shell?.inert ?? false
    if (shell) shell.inert = true
    const controls = () => Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]') ?? []).filter(el => !el.hidden)
    const firstInput = ref.current?.querySelector<HTMLElement>('input,select,textarea')
    ;(firstInput ?? controls()[0])?.focus()
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeRef.current(); return }
      if (event.key !== 'Tab') return
      const items = controls(), first = items[0], last = items.at(-1)
      if (event.shiftKey && (document.activeElement === first || !ref.current?.contains(document.activeElement))) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && (document.activeElement === last || !ref.current?.contains(document.activeElement))) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', key, true)
    return () => { document.removeEventListener('keydown', key, true); if (shell) shell.inert = priorInert; if (previous?.isConnected) previous.focus() }
  }, [])
  return createPortal(<div className="plugin-modal-backdrop plugins-theme" onClick={onClose}><section className={`plugin-modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={id} ref={ref} onClick={e => e.stopPropagation()}><header className="plugin-modal-header"><h2 id={id}>{title}</h2><button aria-label="Close dialog" onClick={onClose}><X size={20} /></button></header>{children}</section></div>, document.body)
}
