import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { fieldOpsStore } from '../src/state/useFieldOps'
import { demoSelection } from '../src/lib/geo'
import { FarmsTab } from '../src/components/sidebar/FarmsTab'
import { FarmDetailPanel } from '../src/components/farms/FarmDetailPanel'
import { OverviewTab } from '../src/components/sidebar/OverviewTab'
import { syntheticFarms } from '../src/demo/synthetic-farms'
beforeEach(() => fieldOpsStore.getState().clearSelection())
describe('sidebar integration', () => {
  it('selection progresses to overview and farm list then focuses a farm', async () => {
    const user = userEvent.setup(); render(<OverviewTab />); await user.click(screen.getByRole('button', { name: /try demo area/i }))
    expect(await screen.findByText('Getting the area ready.')).toBeInTheDocument()
    expect(await screen.findByText('Your area, at a glance.', {}, { timeout: 4000 })).toBeInTheDocument()
    const view = render(<FarmsTab />); expect(screen.getByTestId('farm-list-count')).toHaveTextContent('12 of 12')
    await user.click(screen.getByRole('button', { name: /Demo Farm F-007.*Maize/ }))
    await waitFor(() => expect(fieldOpsStore.getState().selectedFarmId).toBe('F-007'))
    expect(fieldOpsStore.getState().focus).toMatchObject({ type: 'farm', farmIds: ['F-007'] }); view.unmount()
  })
  it('farm cards render reasons, coordinates, missing data and candidate constraints', async () => {
    const user = userEvent.setup(), view = render(<FarmDetailPanel farm={syntheticFarms[6]} />)
    expect(screen.getByText('8.53200° N, 39.28400° E')).toBeInTheDocument()
    expect(screen.getByText(syntheticFarms[6].riskReasons[0])).toBeInTheDocument()
    await user.click(screen.getAllByText('Constraints & evidence')[0]); expect(screen.getByText('Check cultivar, season length, and field water availability.')).toBeVisible()
    view.rerender(<FarmDetailPanel farm={syntheticFarms[8]} />); expect(screen.getByText('pH unavailable')).toBeInTheDocument(); expect(screen.getByText(/Insufficient evidence for crop candidates/)).toBeInTheDocument()
  })
  it('shows retry after failed analysis with selection preserved', () => {
    fieldOpsStore.setState({ selection: demoSelection(), phase: 'failed', error: 'Provider unavailable' })
    render(<OverviewTab />); expect(screen.getByText('Provider unavailable')).toBeInTheDocument(); expect(screen.getByRole('button', { name: /Retry screening/ })).toBeEnabled()
    expect(fieldOpsStore.getState().selection).not.toBeNull()
  })
  it('shows an informative empty area state', async () => {
    fieldOpsStore.setState({ selection: demoSelection(), phase: 'partial', farms: [], analysis: { id: 'empty', selection_id: 'empty', mode: 'mock', status: 'partial', checkedAt: new Date().toISOString(), farms: [], providers: [], evidence: [] } })
    render(<OverviewTab />); expect(screen.getByText('0 farms found')).toBeInTheDocument(); expect(screen.getByRole('button', { name: /Try demo area/ })).toBeEnabled()
  })
})
