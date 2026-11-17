import type { HomeEvidence } from '../../api/home-contracts'
import { evidenceSeries, record, sourceLink } from '../../features/home/evidence'

export function EvidencePanel({ evidence }: { evidence: HomeEvidence }) {
  const data = evidence.data, source = data.source, payload = record(data.values.payload), link = sourceLink(source.url)
  const soil: (Record<string, unknown> & { name: string })[] = Object.entries(record(payload.properties)).flatMap(([name, rows]) => Array.isArray(rows) ? rows.map(row => ({ ...record(row), name })) : [])
  return <section className="live-evidence" aria-label={'Evidence ' + evidence.id}>
    <h4>{source.provider ?? 'Recorded source'} · {data.values.kind}</h4>
    <p><strong>{data.classification}</strong> provider evidence · {data.input_synthetic ? 'synthetic farm context' : 'authorized farm context'} · validation: {data.validation_status}</p>
    <dl><dt>Evidence ID</dt><dd>{evidence.id}</dd><dt>Tool version</dt><dd>{data.tool_version_id}</dd><dt>Farm</dt><dd>{data.plot_id ?? (data.permitted_plot_ids.join(', ') || 'Not farm-specific')}</dd><dt>Retrieved</dt><dd>{data.retrieved_at}</dd><dt>Observation period</dt><dd>{source.valid_time_range ? source.valid_time_range.from + ' — ' + source.valid_time_range.to : source.observed_at ?? 'Not supplied'}</dd></dl>
    {link && <a href={link} target="_blank" rel="noreferrer">Open source reference</a>}
    {soil.length > 0 && <div className="live-table"><table><caption>Mapped soil properties — provider units and uncertainty retained</caption><thead><tr><th>Property</th><th>Value</th><th>Unit</th><th>Depth</th><th>Uncertainty</th></tr></thead><tbody>{soil.map((row, i) => { const v = record(row.value), depth = record(row.depth); return <tr key={i}><th>{row.name}</th><td>{String(v.value ?? 'Not supplied')}</td><td>{String(v.unit ?? 'Not supplied')}</td><td>{String(depth.value ?? '')} {String(depth.unit ?? '')}</td><td>{row.uncertainty ? JSON.stringify(row.uncertainty) : 'Not supplied'}</td></tr> })}</tbody></table></div>}
    {evidenceSeries(evidence).map((series, i) => {
      const points = series.points.slice(0, 60), low = Math.min(...points.map(p => p.value)), high = Math.max(...points.map(p => p.value)), span = high - low || 1
      const coordinates = points.map((p, j) => [20 + j * 440 / Math.max(1, points.length - 1), 110 - (p.value - low) * 90 / span])
      return <figure key={i} className="live-chart"><figcaption>{series.label} {series.unit && '(' + series.unit + ')'}</figcaption>{points.length > 1 && <svg viewBox="0 0 480 140" role="img" aria-label={series.label + ': ' + points.length + ' recorded values'}><polyline points={coordinates.map(p => p.join(',')).join(' ')} fill="none" stroke="currentColor" strokeWidth="2" />{coordinates.map(([x, y], j) => <circle key={j} cx={x} cy={y} r="3"><title>{points[j].date}: {points[j].value} {series.unit}</title></circle>)}<text x="20" y="135">{points[0].date.slice(0, 10)}</text><text x="360" y="135">{points.at(-1)!.date.slice(0, 10)}</text></svg>}<div className="live-table"><table><thead><tr><th>Observation date / period start</th><th>Value</th><th>Unit</th></tr></thead><tbody>{points.map((point, j) => <tr key={j}><td>{point.date}</td><td>{point.value}</td><td>{series.unit || 'Not supplied'}</td></tr>)}</tbody></table></div></figure>
    })}
    <ul>{data.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul>
    <details><summary>Inspect structured provider values and quality metadata</summary><pre>{JSON.stringify(data.values.payload, null, 2)}</pre><pre>{JSON.stringify(source, null, 2)}</pre></details>
  </section>
}
