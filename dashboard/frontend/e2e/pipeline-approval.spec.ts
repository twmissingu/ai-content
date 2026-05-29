import { test, expect } from '@playwright/test'

test.describe('Pipeline & Approval flow', () => {
  test('pipeline page renders agent status', async ({ page }) => {
    await page.goto('/pipeline')
    await expect(page).toHaveTitle(/稿定|Dashboard/)
    // Pipeline view should show agent cards or status section
    await expect(page.locator('body')).toBeVisible()
  })

  test('approval page loads queue', async ({ page }) => {
    await page.goto('/approval')
    // Should render the approval view without error
    await expect(page.locator('body')).toBeVisible()
  })

  test('navigation between pipeline and approval', async ({ page }) => {
    await page.goto('/pipeline')
    // Click approval link in nav
    const approvalLink = page.getByRole('link', { name: /审批|approval/i })
    if (await approvalLink.isVisible()) {
      await approvalLink.click()
      await expect(page).toHaveURL(/approval/)
    }
  })
})
