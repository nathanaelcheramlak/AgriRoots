import { Mail, MessageSquareText, Mic, Smartphone } from 'lucide-react'
import type { CampaignInput, RecipientGroup } from '../../features/outreach/types'
import { channelLabels, eligibilityLabels, languageLabels } from '../../features/outreach/types'
import { groupMessage, renderMessage, smsEstimate } from '../../features/outreach/messages'
import { eligibility, recipientById, resolveRecipients } from '../../features/outreach/recipients'
import { Field } from './OutreachUi'
export function ChannelSelector({ input, onChange }: { input: CampaignInput; onChange: (input: CampaignInput) => void }) {
  const icons = { sms: MessageSquareText, voice: Mic, email: Mail, smartphone: Smartphone }
  return <div className="outreach-channel-selector"><div className="outreach-channel-grid">{Object.entries(channelLabels).map(([id, label]) => { const Icon = icons[id as keyof typeof icons]; return <label key={id} className={input.communication.channel === id ? 'selected' : ''}><input type="radio" name="campaign-channel" aria-label={label} checked={input.communication.channel === id} onChange={() => onChange({ ...input, communication: { ...input.communication, channel: id as CampaignInput['communication']['channel'] }, guidance: { ...input.guidance, groupOverrides: [] } })} /><Icon size={21} /><strong>{label}</strong><small>Not configured</small></label> })}</div>
    <div className="monitor-form-grid"><Field label="Message language"><select aria-label="Message language" value={input.communication.language} onChange={e => onChange({ ...input, communication: { ...input.communication, language: e.target.value as CampaignInput['communication']['language'] }, guidance: { ...input.guidance, groupOverrides: [] } })}><option value="preferred">Use recipient preference</option>{Object.entries(languageLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></Field><Field label="Fallback policy"><select aria-label="Fallback policy" value={input.communication.fallback} onChange={e => onChange({ ...input, communication: { ...input.communication, fallback: e.target.value as CampaignInput['communication']['fallback'] } })}><option value="none">No fallback</option><option value="manual_review">Require a new officer review before fallback</option></select></Field><Field label="Officer-chosen follow-up date (optional)"><input aria-label="Follow-up date" type="date" value={input.communication.followUpDate} onChange={e => onChange({ ...input, communication: { ...input.communication, followUpDate: e.target.value } })} /></Field></div>
    <div className="monitor-info"><p>All communication channels are not configured. Local plugin drafts do not establish working connections. Language choice does not translate text; non-English groups need manually supplied, reviewed wording. No costs or delivery attempts are generated.</p></div>
  </div>
}
export function ChannelPreview({ input, group, recipientId, onRecipient }: { input: CampaignInput; group?: RecipientGroup; recipientId?: string; onRecipient?: (id: string) => void }) {
  const ids = group?.recipientIds ?? resolveRecipients(input).filter(r => r.eligibility.eligible).map(r => r.recipient.id), recipient = recipientById.get(recipientId ?? '') ?? recipientById.get(ids[0])
  const message = group ? groupMessage(group, input) : { body: input.guidance.body, subject: input.guidance.subject, language: 'en' as const }
  const rendered = recipient ? renderMessage(message.body, recipient, input) : { text: message.body, unresolved: [] }, subject = recipient ? renderMessage(message.subject, recipient, input).text : message.subject
  const estimate = smsEstimate(rendered.text), channel = input.communication.channel
  return <aside className="outreach-channel-preview"><div className="outreach-preview-label">PERSONALIZED PREVIEW <span>Not configured</span></div>
    {onRecipient && <Field label="Representative recipient"><select aria-label="Preview recipient" value={recipient?.id ?? ''} onChange={e => onRecipient(e.target.value)}>{ids.slice(0, 50).map(id => <option key={id} value={id}>{recipientById.get(id)?.displayName ?? id}</option>)}</select></Field>}
    <p className="outreach-micro-note">{recipient?.id ?? 'Select an eligible demonstration recipient'} · {languageLabels[message.language]} · {channelLabels[channel]}</p>
    {recipient && <p className="outreach-micro-note">{eligibilityLabels[eligibility(recipient, input).reason]}</p>}
    <div className={'outreach-message-preview preview-' + channel}>
      {channel === 'sms' && <><div className="outreach-phone-notch" /><header><MessageSquareText size={16} />AgriLo · SMS preview</header><div className="outreach-sms-bubble">{rendered.text || 'Your reviewed message will appear here.'}</div><small>Preview only · no phone number stored</small></>}
      {channel === 'voice' && <><header><Mic size={18} />Voice script</header><p>{rendered.text || 'Write an officer-reviewed call script.'}</p><button disabled className="plugin-secondary">No audio artifact available</button><small>No synthesis, call or recording has occurred.</small></>}
      {channel === 'email' && <><header><Mail size={18} />Email preview</header><dl><div><dt>To</dt><dd>{recipient?.displayName ?? 'Demonstration recipient'} · no address stored</dd></div><div><dt>Subject</dt><dd>{subject || 'Add a subject'}</dd></div></dl><p>{rendered.text}</p></>}
      {channel === 'smartphone' && <><header><Smartphone size={18} />Messaging preview</header><div className="outreach-sms-bubble">{rendered.text}</div><small>Provider-specific media and formatting require an approved connector. No attachment was created.</small></>}
    </div>
    {!!rendered.unresolved.length && <p className="outreach-warning-text" role="status">Unresolved: {rendered.unresolved.join(', ')}</p>}
    {channel === 'sms' && <dl className="outreach-sms-estimate"><div><dt>Characters</dt><dd>{estimate.characters}</dd></div><div><dt>Encoding</dt><dd>{estimate.encoding}</dd></div><div><dt>Estimated segments</dt><dd>{estimate.segments}</dd></div><div><dt>Cost</dt><dd>Unavailable</dd></div></dl>}
    <p className="outreach-micro-note">Encoding estimates only. Provider headers, routing and smart encoding can change final segmentation. No pricing data is connected.</p>
    {ids.length > 50 && <p className="outreach-micro-note">First 50 representatives listed. Use Recipients to inspect the full snapshot and its exceptions.</p>}
  </aside>
}
