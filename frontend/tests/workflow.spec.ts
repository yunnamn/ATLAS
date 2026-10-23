import { expect, test } from '@playwright/test'

test('dashboard, live filters, comparison, and evidence review', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'A little direction. A world of possibility.' }),
  ).toBeVisible()
  await expect(page.locator('.opportunity-card')).toHaveCount(3)
  await page.getByRole('link', { name: 'Discover opportunities' }).click()
  await expect(page.locator('.opportunity-card')).toHaveCount(6)
  await page.getByRole('textbox', { name: 'Search directory' }).fill('robotics')
  await expect(page.locator('.opportunity-card')).toHaveCount(1)
  await expect(
    page.getByRole('link', { name: 'Intelligent Robotics Scholarship', exact: true }),
  ).toBeVisible()
  await page.getByRole('textbox', { name: 'Search directory' }).fill('')
  await page.getByLabel('Filter by destination').selectOption('Sweden')
  await expect(page.locator('.opportunity-card')).toHaveCount(1)
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await page.getByLabel('Filter by funding').selectOption('tuition_and_stipend')
  await expect(page.locator('.opportunity-card')).toHaveCount(3)
  await page.getByLabel('Compare opportunity').nth(0).check()
  await page.getByLabel('Compare opportunity').nth(1).check()
  await page.getByRole('button', { name: 'Compare opportunities' }).click()
  await expect(page.getByRole('heading', { name: 'A closer look, side by side.' })).toBeVisible()
  await page.getByRole('link', { name: 'AI for Sustainable Systems', exact: true }).first().click()
  await expect(
    page.getByRole('heading', { name: 'AI for Sustainable Systems', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('This is a synthetic demonstration.', { exact: true })).toBeVisible()
  const field = page.locator('.fact-row').filter({ hasText: 'Application deadline' })
  await field.locator('summary').click()
  await expect(field.locator('blockquote')).toContainText('2027-01-15')
  await field.getByRole('button', { name: 'Review / correct' }).click()
  await page.getByLabel('Verification state').selectOption('verified')
  await page.getByLabel('Recorded value').fill('2027-01-20')
  await page.getByLabel('Supporting excerpt').fill('SYNTHETIC CORRECTION: Deadline 2027-01-20.')
  await page
    .getByLabel('Reason for this correction')
    .fill('Corrected the synthetic demonstration deadline.')
  await page.getByRole('button', { name: 'Save correction' }).click()
  await expect(page.getByText('Revision 2', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Revision history' }).click()
  await expect(
    page.getByText('Corrected the synthetic demonstration deadline.', { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('Changed: Application deadline', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('profile, explainable match, and persistent application tracking', async ({ page }) => {
  await page.goto('/profile')
  await page.getByLabel('Display name').fill('Test researcher')
  await page.getByLabel('Nationality (two-letter ISO code)').fill('UZ')
  await page.getByLabel('Highest completed education').selectOption('bachelor')
  await page.getByLabel('GPA on a 4.0 scale').fill('3.8')
  await page.getByLabel('IELTS overall score').fill('7.5')
  await page.getByLabel('Subject interests (comma-separated)').fill('Artificial intelligence')
  await page.getByLabel('Preferred destinations (comma-separated)').fill('Sweden')
  await page.getByRole('button', { name: 'Save profile & preferences' }).click()
  await expect(page.getByRole('status')).toContainText('Profile saved')
  await page.goto('/opportunities/1')
  await expect(page.locator('.fit-score')).toContainText('100')
  await expect(page.getByText('Eligibility needs review', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Save opportunity', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Saved to shortlist' })).toBeVisible()
  await page.getByRole('link', { name: /My applications/ }).click()
  await page.getByRole('button', { name: 'Manage', exact: true }).click()
  await page.getByLabel('Application status').selectOption('preparing')
  await page
    .getByLabel('Missing requirements (one per line)')
    .fill('Transcript\nLanguage certificate')
  await page.getByLabel('Private research notes').fill('Check the source before applying.')
  await page.getByRole('button', { name: 'Update application' }).click()
  await expect(page.locator('.toast[role=status]')).toContainText('Application updated')
  await page.reload()
  await expect(page.locator('.application-status')).toHaveText('preparing')
  await expect(page.getByText('Transcript', { exact: true })).toBeVisible()
  await expect(page.getByText('Check the source before applying.', { exact: true })).toBeVisible()
})

test('document candidates require review and identity before import', async ({ page }) => {
  await page.goto('/sources')
  await page.getByRole('button', { name: 'Import source' }).first().click()
  await page.getByRole('button', { name: 'PDF / source text' }).click()
  await page
    .getByLabel('Source text', { exact: true })
    .fill('Deadline: 2027-06-01\nFunding: tuition_and_stipend')
  await page.getByRole('button', { name: 'Extract candidates' }).click()
  await expect(page.getByRole('heading', { name: '2 candidate fields extracted' })).toBeVisible()
  await page.getByRole('button', { name: 'Review record JSON' }).click()
  const editor = page.getByLabel('Opportunity JSON')
  const record = JSON.parse(await editor.inputValue())
  Object.assign(record, {
    title: 'Browser test research draft',
    institution: 'Synthetic Browser Institute',
    country: 'Testland',
    summary: 'Synthetic end-to-end import fixture, not a real opportunity.',
    synthetic: true,
  })
  await editor.fill(JSON.stringify(record))
  await page.getByRole('button', { name: 'Validate & import' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByText('Browser test research draft', { exact: true })).toBeVisible()
})

test('mobile navigation and content fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('.opportunity-card')).toHaveCount(3)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('link', { name: 'Discover opportunities' }).click()
  await expect(page.getByRole('textbox', { name: 'Search directory' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/atlas-mobile.png', fullPage: true })
  await page.getByRole('link', { name: 'Profile & preferences', exact: true }).last().click()
  await expect(page.getByRole('heading', { name: 'Your direction, defined.' })).toBeVisible()
})
