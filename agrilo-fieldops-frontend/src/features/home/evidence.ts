import type { HomeEvidence } from '../../api/home-contracts'

export type Series = { label: string; unit: string; points: { date: string; value: number }[] }
export function record(value: unknown): Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }
const numeric = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const unit = (value: unknown) => typeof value === 'string' ? value : ''
function iso(date: string) { return /^\d{8}$/.test(date) ? date.slice(0, 4) + '-' + date.slice(4, 6) + '-' + date.slice(6) : /^\d{2}\/\d{2}\/\d{4}$/.test(date) ? date.slice(6) + '-' + date.slice(0, 2) + '-' + date.slice(3, 5) : date }

export function evidenceSeries(evidence: HomeEvidence): Series[] {
  const payload = record(evidence.data.values.payload), series: Series[] = []
  const daily = record(payload.daily), units = record(payload.units)
  if (Array.isArray(daily.time)) {
    for (const [key, values] of Object.entries(daily)) {
      if (key === 'time' || !Array.isArray(values)) continue
      const points = daily.time.flatMap((date, index) => typeof date === 'string' && numeric(values[index]) ? [{ date, value: values[index] }] : [])
      if (points.length) series.push({ label: key, unit: unit(units[key]), points })
    }
  }
  for (const [key, values] of Object.entries(record(payload.daily_records))) {
    const points = Object.entries(record(values)).filter((entry): entry is [string, number] => numeric(entry[1])).map(([date, value]) => ({ date: iso(date), value }))
    if (points.length) series.push({ label: key, unit: unit(record(record(payload.parameters)[key]).units), points })
  }
  if (Array.isArray(payload.data)) {
    const points = payload.data.flatMap(row => { const r = record(row), avg = record(r.value).avg; return typeof r.date === 'string' && numeric(avg) ? [{ date: iso(r.date), value: avg }] : [] })
    if (points.length) series.push({ label: 'Historical rainfall', unit: unit(payload.units), points })
  }
  if (Array.isArray(payload.observations)) {
    const points = payload.observations.flatMap(row => { const r = record(row); return typeof r.observation_date === 'string' && numeric(r.ndvi) && numeric(r.valid_pixel_count) && r.valid_pixel_count > 0 ? [{ date: r.observation_date, value: r.ndvi }] : [] })
    if (points.length) series.push({ label: 'NDVI — valid quality-filtered composites', unit: unit(evidence.data.source.units), points })
  }
  if (Array.isArray(payload.last_five_prices)) {
    const points = payload.last_five_prices.flatMap(row => { const r = record(row); return typeof r.date === 'string' && numeric(r.price_value) ? [{ date: r.date, value: r.price_value }] : [] })
    const meta = record(payload.series_metadata)
    if (points.length) series.push({ label: unit(meta.commodity_name) + ' · ' + unit(meta.market_name), unit: unit(meta.currency) + ' / ' + unit(meta.measure_unit_label), points })
  }
  if (Array.isArray(payload.records)) {
    const groups = new Map<string, Series>()
    for (const row of payload.records) {
      const r = record(row)
      if (!numeric(r.price) || typeof r.reference_period_start !== 'string') continue
      const key = JSON.stringify([r.commodity_name, r.market_name, r.currency_code, r.unit, r.price_type])
      const item = groups.get(key) ?? { label: unit(r.commodity_name) + ' · ' + unit(r.market_name) + ' · ' + unit(r.price_type), unit: unit(r.currency_code) + ' / ' + unit(r.unit), points: [] }
      item.points.push({ date: r.reference_period_start, value: r.price }); groups.set(key, item)
    }
    series.push(...groups.values())
  }
  return series.map(s => ({ ...s, points: [...s.points].sort((a, b) => a.date.localeCompare(b.date)) }))
}

export function sourceLink(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try { const url = new URL(value); if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return null; url.search = ''; url.hash = ''; return url.toString() } catch { return null }
}
