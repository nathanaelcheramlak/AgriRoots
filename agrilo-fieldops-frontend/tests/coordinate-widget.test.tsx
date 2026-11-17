import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CoordinateWidget } from '../src/components/map/CoordinateWidget'
import { fieldOpsStore } from '../src/state/useFieldOps'
import { areaKm2, demoSelection } from '../src/lib/geo'
beforeEach(() => fieldOpsStore.getState().clearSelection())
describe('coordinate area selection adapted from AgroSphere', () => {
  it('builds a real bounded area around manually selected coordinates', async () => {
    const onCoordinate = vi.fn(), user = userEvent.setup()
    render(<CoordinateWidget coordinate={{ lat: 8.546, lng: 39.273 }} onCoordinate={onCoordinate} />)
    await user.click(screen.getByRole('button', { name: 'Analyze area' }))
    const selection = fieldOpsStore.getState().selection!
    expect(selection.client_context.trigger).toBe('manual_area')
    expect((selection.bbox[0] + selection.bbox[2]) / 2).toBeCloseTo(39.273, 8)
    expect((selection.bbox[1] + selection.bbox[3]) / 2).toBeCloseTo(8.546, 8)
    expect(areaKm2(selection.bbox)).toBeCloseTo(100, 3)
    expect(selection.geometry.coordinates[0][0]).toEqual([selection.bbox[0], selection.bbox[1]])
    expect(fieldOpsStore.getState().focus.type).toBe('selection')
    expect(onCoordinate).toHaveBeenCalledWith({ lat: 8.546, lng: 39.273 })
    fieldOpsStore.getState().clearSelection()
  })
  it('preserves the last area when manual bounds exceed the geometry guard', async () => {
    const s = demoSelection(); fieldOpsStore.getState().setSelection(s, 0)
    const user = userEvent.setup()
    render(<CoordinateWidget coordinate={{ lat: 89, lng: 39 }} onCoordinate={() => {}} />)
    await user.clear(screen.getByRole('spinbutton', { name: 'Area width in kilometres' }))
    await user.type(screen.getByRole('spinbutton', { name: 'Area width in kilometres' }), '40')
    await user.click(screen.getByRole('button', { name: 'Analyze area' }))
    expect(fieldOpsStore.getState().selection?.selection_id).toBe(s.selection_id)
    expect(fieldOpsStore.getState().toast).toContain('Area is too large')
    fieldOpsStore.getState().clearSelection()
  })
})
