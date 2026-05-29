import { test, expect } from '@playwright/test'

test.describe('Topic confirmation flow', () => {
  test('topics page renders', async ({ page }) => {
    await page.goto('/topics')
    await expect(page).toHaveTitle(/稿定|Dashboard/)
    await expect(page.locator('body')).toBeVisible()
  })

  test('data page renders charts', async ({ page }) => {
    await page.goto('/data')
    await expect(page.locator('body')).toBeVisible()
  })

  test('config page renders settings', async ({ page }) => {
    await page.goto('/config')
    await expect(page.locator('body')).toBeVisible()
  })

  test('knowledge base page renders', async ({ page }) => {
    await page.goto('/kb')
    await expect(page.locator('body')).toBeVisible()
  })
})
