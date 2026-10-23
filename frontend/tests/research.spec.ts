import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('offline research revises its plan, reports evidence, and opens the actual saved source', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/research')
  await expect(page.getByRole('heading', { name: 'Research with a clear trail.' })).toBeVisible()
  await page.getByRole('button', { name: 'Start offline demo' }).click()
  await expect(page.locator('.research-plan-revision')).toHaveText('Revision 2')
  await expect(page.locator('.research-timeline article')).toHaveCount(12)
  await expect(page.locator('.research-timeline')).toContainText(
    'proof-of-funds evidence is missing',
  )
  await expect(page.locator('.research-run-stats')).toContainText('0 real model requests')
  await page.getByRole('button', { name: 'Report', exact: true }).click()
  await expect(page.locator('.report-summary')).toContainText('SYNTHETIC OFFLINE DEMONSTRATION')
  await expect(page.getByRole('heading', { name: 'Research report', exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^Evidence & sources/ }).click()
  await expect(page.locator('.research-claim')).toHaveCount(14)
  await page.getByRole('button', { name: 'Inspect supporting citation' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Saved source inspector' })
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('.selected-excerpt blockquote')).not.toBeEmpty()
  await dialog.getByText('Inspect full saved text', { exact: false }).click()
  await expect(dialog.locator('pre')).toContainText('SYNTHETIC OFFLINE DEMO')
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await page.reload()
  await expect(page.locator('.research-plan-revision')).toHaveText('Revision 2')
  expect(errors).toEqual([])
})

test('insufficient evidence stays unknown in the report on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/research')
  await page.getByLabel('Demonstration scenario').selectOption('insufficient')
  await page.getByRole('button', { name: 'Start offline demo' }).click()
  await expect(page.getByRole('button', { name: 'Read partial report' })).toBeVisible()
  await page.getByRole('button', { name: 'Report', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Partial research report', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.unanswered-line')).toContainText('Proof of funds')
  await expect(page.locator('.unanswered-line')).toContainText('Unknown')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
})

test('conflicting sources retain both cited values and yield a partial report', async ({
  page,
}) => {
  await page.goto('/research')
  await page.getByLabel('Demonstration scenario').selectOption('conflict')
  await page.getByRole('button', { name: 'Start offline demo' }).click()
  await expect(page.getByRole('button', { name: 'Read partial report' })).toBeVisible()
  await page.getByRole('button', { name: /^Evidence & sources/ }).click()
  await expect(page.locator('.research-conflicts > p')).toHaveCount(2)
  await expect(page.locator('.research-claim .research-contradictory')).toHaveCount(4)
  await expect(page.locator('.research-claim')).toContainText(['full tuition'])
  await expect(page.getByText('tuition not covered', { exact: true })).toBeVisible()
})

test('live mode discloses model use and cannot start without configuration', async ({ page }) => {
  await page.goto('/research')
  await page.getByLabel('Research mode').selectOption('live')
  await expect(page.getByText('Live provider is not configured.', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start live research' })).toBeDisabled()
  await page.getByRole('checkbox').check()
  await expect(page.getByRole('button', { name: 'Start live research' })).toBeDisabled()
  await expect(page.getByText('Broader search:', { exact: false })).toContainText('not configured')
})
