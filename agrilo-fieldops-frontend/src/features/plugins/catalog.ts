import snapshot from './catalog-snapshot.json'
import type { CatalogItem, PluginCategory } from './types'

const descriptions: Record<string, string> = {
  open_meteo: 'Forecasts and weather context for field planning.', nasa_power: 'Historical climate, rainfall, and solar context.', chirps: 'Historical rainfall estimates for a selected area.', isda_soil: 'Mapped soil profiles, properties, and uncertainty.',
  fao_wapor: 'Evapotranspiration and water-use reference data.', copernicus: 'Sentinel imagery and vegetation information.', fao_fpma: 'Ethiopian commodity and market-price context.', nasa_power_mcp: 'NASA climate data through an HTTP MCP server.',
  fao_gaez: 'Crop-suitability datasets and reference catalogs.', google_earth_engine: 'Geospatial datasets and satellite processing.', fao_asis: 'Agricultural stress and vegetation-condition context.', deepleaf: 'Crop-image assessment provider configuration.',
  kindwise: 'Crop-health candidate identification from images.', plantix: 'Partner crop-image assessment services.', fao_locust: 'Reported locust observations and regional context.', eppo: 'Pest taxonomy and reference information.',
  cabi: 'Country-specific pest-management reference guides.', wfp_prices: 'Food prices and market-monitoring datasets.', openrouteservice: 'Road routes and travel context for field visits.', kobotoolbox: 'Field forms and project-collection workflows.',
  odk_central: 'Connect an office’s own field-data server.', africas_talking: 'Communication-provider configuration for a future phase.',
}
const limitations: Record<string, string> = {
  fao_wapor: 'Raster and range-data integration is not available in this frontend.', nasa_power_mcp: 'MCP discovery and connection checks require the future backend.', fao_gaez: 'Dataset discovery does not establish numerical crop suitability.',
  fao_asis: 'Raster extraction remains unavailable; catalog access is not a vegetation assessment.', kindwise: 'Requires a future authorized image workflow, provider access, and credit-use controls.',
  plantix: 'Requires issued partner access; no credential or diagnosis capability is supplied here.', odk_central: 'Requires your own Central server and an authorized backend connection.',
  africas_talking: 'Sending notifications is outside this phase. No messaging capability is enabled.',
}
export const pluginCatalog: CatalogItem[] = snapshot.items.map(item => ({
  id: item.id, name: item.name, description: descriptions[item.id], category: item.category as PluginCategory,
  source: 'built_in', resourceKind: 'provider', ownerScope: 'system', docsUrl: item.docsUrl, authRequired: item.authRequired,
  availability: item.hasTemplate ? (item.authRequired ? 'setup_required' : 'setup_available') : item.authRequired ? 'setup_required' : 'unavailable',
  requirement: limitations[item.id] ?? (item.authRequired ? 'Provider account or access is required. Save a draft now; credential setup and integration support require a future backend.' : 'A provider template is listed. Saving it locally does not connect it or enable its tools.'),
  snapshotDate: snapshot.snapshotDate,
}))
