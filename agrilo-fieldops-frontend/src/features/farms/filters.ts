import type { Farm, Filters } from '../../api/types'
export const emptyFilters: Filters = { risk: '', crop: '', candidateCrop: '', drought: '', search: '' }
export function filterFarms(farms: Farm[], f: Filters): Farm[] {
  return farms.filter(farm => (!f.risk || farm.riskLevel === f.risk) && (!f.crop || farm.currentCrop.toLowerCase() === f.crop.toLowerCase()) && (!f.candidateCrop || farm.candidates.some(c => c.crop.toLowerCase() === f.candidateCrop.toLowerCase() && c.status !== 'not_recommended')) && (!f.drought || farm.droughtRisk === f.drought) && (!f.search || `${farm.id} ${farm.displayName} ${farm.currentCrop}`.toLowerCase().includes(f.search.toLowerCase())))
}
