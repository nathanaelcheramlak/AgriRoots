export const dateTime = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Africa/Addis_Ababa' }).format(new Date(value))
export const titleCase = (text: string) => text.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase())
export function errorMessage(e: unknown): string { return e instanceof Error ? e.message : 'Something went wrong. Please retry.' }
