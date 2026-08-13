import { expect, test } from '@playwright/test'

test('creates a project and opens the studio workspace', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
  await page.getByRole('button', { name: 'New project' }).first().click()

  await page.getByLabel('New project name').fill('Playwright Main Menu')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByRole('heading', { name: 'Playwright Main Menu' })).toBeVisible()
  await expect(page.getByTestId('studio-canvas')).toBeVisible()

  await page.getByRole('button', { name: 'Back to projects' }).click()
  await expect(page.getByRole('heading', { name: 'Playwright Main Menu' })).toBeVisible()
})

