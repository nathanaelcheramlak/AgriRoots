import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RecipientPicker } from '../src/components/outreach/RecipientPicker'
import { ChannelPreview } from '../src/components/outreach/ChannelPreview'
import { newCampaignInput } from '../src/features/outreach/catalog'
describe('Outreach interaction components', () => {
  it('renders only one recipient page and preserves selected people while changing pages', () => {
    function Picker() { const [input, setInput] = useState(newCampaignInput('weekly')); return <RecipientPicker input={input} onChange={setInput} /> }
    render(<Picker />)
    expect(screen.getAllByRole('checkbox')).toHaveLength(20)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select DEMO-P0003' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next recipient page' }))
    expect(screen.getByRole('checkbox', { name: 'Select DEMO-P0021' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Previous recipient page' }))
    expect(screen.getByRole('checkbox', { name: 'Select DEMO-P0003' })).toBeChecked()
  })
  it('renders personalized content as text without executing arbitrary HTML', () => {
    const input = newCampaignInput('weekly'); input.selection.ids = ['DEMO-P0003']; input.guidance.body = '<img src=x onerror=alert(1)> {{farmer_name}}'
    const { container } = render(<ChannelPreview input={input} />)
    expect(screen.getByText('<img src=x onerror=alert(1)> Demo farmer 0003')).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('Not configured')).toBeInTheDocument()
  })
})
