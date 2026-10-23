import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const route of [
  '/',
  '/opportunities',
  '/opportunities/1',
  '/profile',
  '/sources',
  '/saved',
  '/research',
]) {
  test(`main screen accessibility: ${route}`, async ({ page }) => {
    await page.goto(route)
    await page.waitForLoadState('networkidle')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(results.violations).toEqual([])
  })
}

test('keyboard import dialog and evidence correction accessibility', async ({ page }) => {
  await page.goto('/opportunities/1')
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: 'Import source' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  let results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(results.violations).toEqual([])
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const field = page.locator('.fact-row').filter({ hasText: 'Funding coverage' })
  await field.locator('summary').click()
  await field.getByRole('button', { name: 'Review / correct' }).click()
  results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(results.violations).toEqual([])
})
