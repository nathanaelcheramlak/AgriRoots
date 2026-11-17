import type { FarmerProfile, Territory } from './types'
import { rectangle } from './geometry'
export const demoTerritory: Territory = { id: 'synthetic-territory-adama', name: 'Demo · Adama East', region: 'Demo Oromia', district: 'Demo Adama', description: 'Synthetic planning boundary, not an assigned territory.', status: 'local-draft', origin: 'synthetic', boundary: rectangle(39.218, 8.502, 39.328, 8.59), createdAt: '2026-01-01T00:00:00Z' }
export function syntheticFarmer(i: number): FarmerProfile {
  return { id: `DEMO-FARMER-${String(i).padStart(4, '0')}`, reference: `DEMO-REF-${String(i).padStart(4, '0')}`, displayName: `Synthetic Farmer ${String(i).padStart(4, '0')}`, village: `Demo Village ${i % 12 + 1}`, household: '', language: ['English', 'Amharic', 'Afaan Oromo'][i % 3], channel: ['sms', 'voice', 'smartphone', 'email', 'none', 'in-person'][i % 6] as FarmerProfile['channel'], availability: i % 7 ? 'available' : 'unknown', consent: 'unknown', verification: 'verified-demo', phone: '', email: '', preferences: '', notes: 'Synthetic demonstration profile.', origin: 'synthetic' }
}
export const demoFarmers = Array.from({ length: 2000 }, (_, i) => syntheticFarmer(i + 1))
