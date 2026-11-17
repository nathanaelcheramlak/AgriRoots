import { test, expect, type Page } from '@playwright/test'
import { context, job, result, evidence, plotId } from '../tests/home-fixtures'

async function openFixture(page: Page) {
  const fixtureContext = structuredClone(context)
  fixtureContext.office_name = 'AgriLo layout fixture office'
  fixtureContext.role = 'office_admin'
  fixtureContext.skills[0].tools[0].input_schema = { type: 'object', properties: { resume_invocation_id: { type: 'string' }, start: { type: 'string', format: 'date' }, end: { type: 'string', format: 'date' } } }
  fixtureContext.plots = Array.from({ length: 18 }, (_, i) => ({ ...context.plots[0], id: i ? `fixture-plot-${i}` : plotId, name: `Fixture farm ${i + 1}` }))
  await page.route('https://**/*', route => route.abort())
  await page.route('**/backend/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/backend', '')
    const completed = { ...job, status: 'succeeded', result: { ...result, answer: Array(25).fill(result.answer).join('\n\n') } }
    if (path === '/api/auth/login') return route.fulfill({ json: { access_token: 'layout-fixture-only', token_type: 'bearer', user: { user_id: context.user_id } } })
    if (path === '/api/v1/companion/context') return route.fulfill({ json: fixtureContext })
    if (path.endsWith('/runs') || path.includes('/connector-jobs/')) return route.fulfill({ json: completed })
    if (path.includes('/evidence/')) return route.fulfill({ json: evidence })
    if (path === '/api/v1/providers') return route.fulfill({ json: { items: [{ id: 'fixture-provider', name: 'Fixture agricultural provider', category: 'weather', handler_id: 'fixture', implemented: true, implemented_capabilities: ['weather.forecast'], implementation_blocker: null, historical_verification: { status: 'NOT_TESTED' } }] } })
    if (path === '/api/v1/integrations') return route.fulfill({ json: { items: [] } })
    return route.fulfill({ status: 404, json: { detail: 'Unexpected layout fixture route' } })
  })
  await page.goto('/#home')
  await page.getByLabel('Phone number', { exact: true }).fill('layout-fixture')
  await page.getByLabel('Password', { exact: true }).fill('layout-fixture-only')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('main', { name: 'Live officer companion' })).toBeVisible()
  await expect(page.locator('.field-map')).toBeVisible()
}
async function navigate(page: Page, name: string) {
  if (await page.getByRole('button', { name: 'Open navigation', exact: true }).isVisible()) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await page.getByRole('link', { name, exact: true }).click()
}
async function noHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1280, height: 600 }, { width: 820, height: 720 }]) {
  test(`Home fits at normal zoom, including expanded map and long results (${viewport.width}×${viewport.height})`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await openFixture(page)
    const start = page.getByRole('button', { name: 'Start investigation', exact: true })
    await expect(start).toBeInViewport({ ratio: 1 })
    await expect(page.getByLabel('Agricultural question', { exact: true })).toBeInViewport({ ratio: 1 })
    await expect(page.getByRole('button', { name: 'Draw rectangle', exact: true })).toBeInViewport({ ratio: 1 })
    await page.getByRole('checkbox', { name: /Fixture farm 1\b/ }).check()
    await page.getByRole('button', { name: 'Expand map', exact: true }).click()
    const pane = await page.locator('.live-map-panel').boundingBox()
    const main = await page.locator('.live-workspace').boundingBox()
    expect(Math.abs(pane!.width - main!.width)).toBeLessThan(2)
    await expect(start).toBeInViewport({ ratio: 1 })
    await page.getByRole('checkbox', { name: /Authorize the selected skill/ }).check()
    await page.getByRole('checkbox', { name: /Authorize the backend-configured model/ }).check()
    await page.getByLabel('Agricultural question', { exact: true }).fill('Inspect the fixture weather and soil evidence.')
    await start.click()
    await expect(page.locator('.live-evidence')).toHaveCount(1)
    await page.locator('.live-workspace-body').evaluate(el => { el.scrollTop = el.scrollHeight })
    await expect(start).toBeInViewport({ ratio: 1 })
    await noHorizontalOverflow(page)
    await page.screenshot({ path: `test-results-layout/home-layout-${viewport.width}.png` })
  })
}

test('Home and all workspaces share the theme, and navigation preserves Home state', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await openFixture(page)
  await page.getByLabel('Filter farms', { exact: true }).fill('Fixture farm 1')
  await page.getByRole('checkbox', { name: /Fixture farm 1\b/ }).check()
  await page.getByLabel('Agricultural question', { exact: true }).fill('Keep my draft question while navigating.')
  await page.getByLabel('LAT', { exact: true }).fill('9.03')
  await page.getByLabel('LNG', { exact: true }).fill('38.74')
  await page.getByRole('button', { name: 'Filter map area', exact: true }).click()
  const geometry = await page.locator('.selection-card').innerText()
  const input = await page.getByLabel('Agricultural skill', { exact: true }).evaluate(el => ({ bg: getComputedStyle(el).backgroundColor, font: getComputedStyle(el).fontFamily }))
  const homeBg = await page.locator('.live-home').evaluate(el => getComputedStyle(el).backgroundColor)
  for (const [name, selector] of [['Plugins', '.plugins-main'], ['Monitoring', '.monitoring-main'], ['Outreach', '.outreach-main']]) {
    await navigate(page, name)
    await expect(page.locator(selector)).toBeVisible()
    expect(await page.locator(selector).evaluate(el => getComputedStyle(el).backgroundColor)).toBe(homeBg)
    await noHorizontalOverflow(page)
    if (name === 'Plugins') {
      await page.screenshot({ path: 'test-results-layout/plugins-layout.png' })
      await page.getByRole('button', { name: 'Add', exact: true }).click()
      await page.getByRole('button', { name: 'Register custom REST API', exact: true }).click()
      const pluginInput = await page.getByRole('dialog').getByLabel('Name', { exact: true }).evaluate(el => ({ bg: getComputedStyle(el).backgroundColor, font: getComputedStyle(el).fontFamily }))
      expect(input).toEqual(pluginInput)
      await page.keyboard.press('Escape')
    }
  }
  await navigate(page, 'Home')
  await expect(page.getByRole('checkbox', { name: /Fixture farm 1\b/ })).toBeChecked()
  await expect(page.getByLabel('Filter farms', { exact: true })).toHaveValue('Fixture farm 1')
  await expect(page.getByLabel('Agricultural question', { exact: true })).toHaveValue('Keep my draft question while navigating.')
  await expect(page.locator('.selection-card')).toHaveText(geometry, { useInnerText: true })
  await expect(page.locator('.field-map')).toBeVisible()
  await page.locator('.live-map-panel').evaluate(el => { el.scrollTop = 0 })
  await page.screenshot({ path: 'test-results-layout/home-layout-ready.png' })
})

test('mobile Home uses natural page scrolling and every action remains reachable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openFixture(page)
  await page.getByRole('button', { name: 'Expand map', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Draw rectangle', exact: true })).toBeVisible()
  await page.getByRole('checkbox', { name: /Fixture farm 1\b/ }).check()
  const question = page.getByLabel('Agricultural question', { exact: true })
  await question.fill('A draft from the mobile officer.')
  const start = page.getByRole('button', { name: 'Start investigation', exact: true })
  await start.scrollIntoViewIfNeeded()
  await expect(start).toBeInViewport({ ratio: 1 })
  await noHorizontalOverflow(page)
  await page.screenshot({ path: 'test-results-layout/home-layout-mobile.png' })
  await navigate(page, 'Plugins')
  await noHorizontalOverflow(page)
  await navigate(page, 'Home')
  await expect(question).toHaveValue('A draft from the mobile officer.')
  await expect(page.getByRole('checkbox', { name: /Fixture farm 1\b/ })).toBeChecked()
})
