import { expect, test } from '@playwright/test'
import { unlink } from 'node:fs/promises'
import path from 'node:path'

test('walk through Prompting Lab without starting an experiment', async ({ page }, testInfo) => {
  const runRequests: string[] = []
  let uploadedDatasetPath: string | undefined
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/experiments/run')) {
      runRequests.push(request.url())
    }
  })

  try {
    await page.goto('/')
    await expect(page).toHaveTitle('Prompting Lab | LLM Evaluation')
    await expect(page.getByText('API connected')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Run an experiment' })).toBeVisible()

    await page.getByLabel('Dataset').selectOption('dataset.jsonl')
    await page.getByLabel('Runs per technique').fill('1')
    await page.getByLabel('Model name').fill('e2e-demo-model')
    await page.getByLabel('Temperature').fill('0.4')
    await page.getByLabel('Max tokens').fill('64')
    await page.getByRole('checkbox', { name: 'Chain of thought' }).uncheck()
    await expect(page.getByRole('checkbox', { name: 'Few-shot' })).toBeChecked()
    await page.waitForTimeout(500)

    await page.getByRole('button', { name: /^Experiments/ }).click()
    await expect(page.getByRole('heading', { name: 'Experiments', exact: true })).toBeVisible()
    const completedExperiment = page.locator('.experiment-item').filter({
      has: page.locator('.status-done'),
    }).first()
    await expect(completedExperiment).toBeVisible()
    await completedExperiment.getByRole('button', { name: 'Files' }).click()
    await expect(completedExperiment.getByRole('heading', { name: 'Generated files' })).toBeVisible()

    const metadataRow = completedExperiment.locator('li').filter({ hasText: 'metadata.json' }).first()
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      metadataRow.getByRole('button', { name: 'Download' }).click(),
    ])
    expect(download.suggestedFilename()).toBe('metadata.json')
    await download.saveAs(testInfo.outputPath('downloaded-metadata.json'))

    await completedExperiment.getByRole('button', { name: 'Delete' }).click()
    const deleteDialog = page.getByRole('dialog')
    await expect(deleteDialog).toBeVisible()
    await expect(deleteDialog.getByRole('heading', { name: 'Delete this experiment?' })).toBeVisible()
    await deleteDialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(deleteDialog).toBeHidden()

    const runningExperiment = page.locator('.experiment-item').filter({
      has: page.locator('.status-running'),
    }).first()
    if (await runningExperiment.count()) {
      await expect(runningExperiment.getByRole('button', { name: 'Delete' })).toBeDisabled()
    }
    await page.waitForTimeout(500)

    await page.getByRole('button', { name: /^Datasets/ }).click()
    await expect(page.getByRole('heading', { name: 'Datasets', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Record format' })).toBeVisible()

    const fixturePath = path.join(__dirname, 'fixtures', 'demo-dataset.jsonl')
    const uploadResponsePromise = page.waitForResponse((response) =>
      response.url().endsWith('/datasets/upload') && response.request().method() === 'POST',
    )
    await page.locator('input[type="file"]').setInputFiles(fixturePath)
    const uploadResponse = await uploadResponsePromise
    expect(uploadResponse.ok()).toBeTruthy()
    const uploadResult = await uploadResponse.json() as { dataset_path: string; filename: string }
    uploadedDatasetPath = uploadResult.dataset_path

    await expect(page.getByRole('status')).toContainText(`Uploaded ${uploadResult.filename}`)
    await expect(page.locator('.dataset-list')).toContainText(uploadResult.filename)
    await page.waitForTimeout(700)
    expect(runRequests).toHaveLength(0)
  } finally {
    if (uploadedDatasetPath) {
      const datasetRoot = path.resolve(__dirname, '../../Backend/datasets')
      const uploadedFilename = path.basename(uploadedDatasetPath)
      if (/^\d+_[a-f0-9]{8}_demo-dataset\.jsonl$/i.test(uploadedFilename)) {
        const resolvedUpload = path.join(datasetRoot, uploadedFilename)
        await unlink(resolvedUpload).catch((error: NodeJS.ErrnoException) => {
          if (error.code !== 'ENOENT') throw error
        })
      }
    }
  }
})