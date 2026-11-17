import type { AssistantContext, AssistantResponse, MapCommand } from '../../api/types'
import { assistantResponseSchema } from '../../api/schemas'

export function parseAssistant(input: string, ctx: AssistantContext): AssistantResponse {
  const q = input.trim().toLowerCase().replace(/[?!.,]+$/, '')
  let text = '', commands: MapCommand[] = []
  if (!ctx.selection || ctx.farms.length === 0) return { text: 'Select an area with registered demo farms first. Try the demo area near Adama.', commands: [] }
  const farmId = q.match(/f-\d{3}/i)?.[0].toUpperCase()
  const farm = ctx.farms.find(f => f.id === (farmId ?? ctx.selectedFarmId))
  if (/^(show|hide) (soil|rainfall|satellite|pests?)( layer)?$/.test(q)) {
    text = 'That geographic layer is unavailable. The backend must provide actual features or licensed tiles before it can be displayed. Farm evidence is available in the detail panel.'
  } else if (q === 'clear filters' || q === 'show all farms') {
    commands = [{ type: 'clear_filters' }]; text = `Filters cleared. All ${ctx.farms.length} farms in this area are visible.`
  } else if (/^(show|hide) (the )?(farm locations|selection)( layer)?$/.test(q)) {
    const layerId = q.includes('selection') ? 'selection' : 'farms'
    commands = [{ type: 'set_layer_visibility', layerId, visible: q.startsWith('show') }]; text = `${layerId === 'farms' ? 'Farm locations' : 'Selection boundary'} ${q.startsWith('show') ? 'shown' : 'hidden'}.`
  } else if (/^(show|show only) (high|moderate|low|unknown)[ -](risk|priority) farms$/.test(q)) {
    const risk = q.match(/(high|moderate|low|unknown)/)![1] as 'high' | 'moderate' | 'low' | 'unknown'
    const farms = ctx.farms.filter(f => f.riskLevel === risk)
    commands = [{ type: 'filter_farms', risk }, { type: 'zoom_to_farms', farmIds: farms.map(f => f.id) }]
    text = `Showing ${farms.length} ${risk}-priority farms from the synthetic records. This classification is illustrative.`
  } else if (/^show (only )?(maize|teff|wheat|sorghum|vegetables) farms$/.test(q)) {
    const crop = q.match(/(maize|teff|wheat|sorghum|vegetables)/)![1]
    commands = [{ type: 'filter_farms', crop }]; text = `Showing ${ctx.farms.filter(f => f.currentCrop.toLowerCase() === crop).length} farms currently growing ${crop}.`
  } else if (/^(which farms are candidates for|show( only)? candidates for) (sorghum|teff|maize|vegetables|chickpea)$/.test(q)) {
    const crop = q.split(' ').at(-1)!
    commands = [{ type: 'filter_farms', candidateCrop: crop }]
    text = `${ctx.farms.filter(f => f.candidates.some(c => c.crop.toLowerCase() === crop && c.status !== 'not_recommended')).length} farms have ${crop} as an illustrative candidate. Review each farm’s evidence and constraints with an agronomist.`
  } else if (/^(zoom to|select) (farm )?f-\d{3}$/.test(q)) {
    if (farm) { commands = [{ type: 'select_farm', farmId: farm.id }]; text = `Selected ${farm.displayName}. Its evidence is in the Farms tab.` }
    else text = `${farmId} is not in the selected area.`
  } else if (q === 'summarize this area' || q === 'summarise this area') {
    text = `${ctx.farms.length} synthetic farms: ${ctx.farms.filter(f => f.riskLevel === 'high').length} high, ${ctx.farms.filter(f => f.riskLevel === 'moderate').length} moderate, ${ctx.farms.filter(f => f.riskLevel === 'low').length} low, ${ctx.farms.filter(f => f.riskLevel === 'unknown').length} unknown priority. Crops: ${[...new Set(ctx.farms.map(f => f.currentCrop))].join(', ')}. Sources: ${ctx.providers.map(p => `${p.name} ${p.status}`).join('; ')}. Fixture evidence is dated July 2026, not current conditions.`
  } else if (/^explain why (farm )?f-\d{3}( is (high|moderate|low|unknown) risk)?$/.test(q) || q === 'explain this farm') {
    text = farm ? `${farm.displayName} · ${farm.riskLevel} priority. ${farm.riskReasons.join(' ')} Evidence: ${farm.evidence.map(e => `${e.id} (${e.status})`).join(', ')}. Synthetic, unvalidated assessment.` : `${farmId ?? 'This farm'} is not in the selected area. Select a farm first.`
  } else if (q === 'fit to selection') { commands = [{ type: 'fit_to_selection' }]; text = 'Map fitted to the current selection.' }
  else text = 'I’m a deterministic demo assistant. Try “Show high-risk farms”, “Show only maize farms”, “Which farms are candidates for sorghum?”, “Zoom to farm F-007”, “Explain this farm”, “Clear filters”, or “Summarize this area”.'
  return assistantResponseSchema.parse({ text, commands })
}
