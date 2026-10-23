import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('research proposal preserves evidence and requires explicit selected-field approval', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/api/opportunities')).json()).total
  await page.goto('/research')
  await page.getByRole('button', { name: 'Start offline demo' }).click()
  await page.getByRole('button', { name: 'Review changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Review proposed changes' })).toBeVisible()
  await page.getByLabel('Unique record identifier').fill(`e2e-reviewed-${Date.now()}`)
  await page.getByLabel('Destination country').fill('Synthetic demonstration')
  await page
    .getByLabel('Record summary')
    .fill('Synthetic research reviewed during a browser integration test.')
  await page.getByRole('button', { name: 'Prepare review proposal' }).click()
  const proposal = page.locator('.research-proposal').first()
  await expect(proposal.getByRole('button', { name: 'Approve selected changes' })).toBeDisabled()
  expect((await (await request.get('/api/opportunities')).json()).total).toBe(before)
  await proposal.getByRole('checkbox', { name: /Tuition coverage/ }).check()
  await proposal.getByText('Inspect evidence for Tuition coverage', { exact: true }).click()
  await proposal.getByRole('button', { name: 'Inspect full saved source' }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await proposal.getByLabel('Reviewer name').fill('Browser reviewer')
  await proposal
    .getByLabel('Review reason')
    .fill('Inspected the exact source, program scope and proposed value.')
  await proposal.getByRole('checkbox', { name: /I inspected the selected citations/ }).check()
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
  await proposal.getByRole('button', { name: 'Approve selected changes' }).click()
  await expect(page.getByRole('link', { name: 'Open saved opportunity' })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Review changes', exact: true }).click()
  await expect(page.getByText('Approved by Browser reviewer.', { exact: false })).toBeVisible()
  const response = await (await request.get('/api/opportunities?q=Lumen')).json()
  const row = response.items[0]
  expect(row.synthetic).toBe(true)
  expect(row.facts.tuition.state).toBe('verified')
  expect(row.facts.stipend.state).toBe('unknown')
  expect(row.facts.language_requirements.state).toBe('unknown')
  const history = await (await request.get(`/api/opportunities/${row.id}/history`)).json()
  expect(history[0].actor).toBe('Browser reviewer')
  await page.getByRole('link', { name: 'Open saved opportunity' }).click()
  await expect(page.getByRole('heading', { name: "Lumen AI Master's", exact: true })).toBeVisible()
})

test('mobile review shows conflicts excluded and prevents approving an unchecked proposal', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/research')
  await page.getByLabel('Demonstration scenario').selectOption('conflict')
  await page.getByRole('button', { name: 'Start offline demo' }).click()
  await page.getByRole('button', { name: 'Review changes', exact: true }).click()
  await page.getByLabel('Save destination').selectOption('1')
  await page.getByRole('button', { name: 'Prepare review proposal' }).click()
  const proposal = page.locator('.research-proposal').first()
  await expect(proposal).toContainText('Update opportunity #1')
  await proposal.getByText('Fields excluded from approval').click()
  await expect(proposal).toContainText('Unsupported, conflicting')
  await expect(proposal.getByRole('checkbox', { name: /Tuition coverage/ })).toHaveCount(0)
  await expect(proposal.getByRole('button', { name: 'Approve selected changes' })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
})
