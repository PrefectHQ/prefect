import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import V1UiRemovalBanner from '@/components/V1UiRemovalBanner.vue'
import { Settings } from '@/services/uiSettings'
import { SlotContainer } from 'tests/SlotContainer'

const { uiSettings, dismissed } = vi.hoisted(() => ({
  uiSettings: { settings: null as Settings | null },
  dismissed: { value: false },
}))

vi.mock('vue-router', () => ({ useRoute: () => ({ path: '/' }) }))
vi.mock('@/services/uiSettings', () => ({
  UiSettings: {
    get settings() {
      return uiSettings.settings
    },
    loadOptional: () => Promise.resolve(uiSettings.settings),
  },
}))
vi.mock('@/utilities/uiVersion', () => ({
  isUiAvailable: (settings: Settings, version: 'v1' | 'v2') => settings.availableUis.includes(version),
  switchToV2Ui: vi.fn(),
}))
vi.mock('@prefecthq/prefect-design', async () => {
  const { SlotContainer: Container } = await import('tests/SlotContainer')
  return { PButton: Container }
})
vi.mock('@prefecthq/vue-compositions', async () => {
  const { ref } = await import('vue')
  return {
    useStorage: (location: string, _key: string, fallback: boolean) => {
      expect(location).toBe('session')
      return { value: ref(dismissed.value || fallback) }
    },
  }
})

function settingsWith(availableUis: Settings['availableUis']): Settings {
  return {
    apiUrl: '/api',
    csrfEnabled: false,
    auth: null,
    flags: [],
    defaultUi: 'v1',
    availableUis,
    v1BaseUrl: '/',
    v2BaseUrl: availableUis.includes('v2') ? '/v2' : null,
  }
}

async function render(): Promise<string> {
  const app = createSSRApp(V1UiRemovalBanner)
  app.component('PButton', SlotContainer)
  return await renderToString(app)
}

beforeEach(() => {
  uiSettings.settings = null
  dismissed.value = false
})

describe('V1UiRemovalBanner', () => {
  it('announces the V1 UI removal version', async () => {
    const page = await render()

    expect(page).toContain('The V1 UI will be removed in Prefect 3.10')
    expect(page).toContain('Dismiss')
  })

  it('offers a switch to the V2 UI when it is available', async () => {
    uiSettings.settings = settingsWith(['v1', 'v2'])

    const page = await render()

    expect(page).toContain('Switch to V2 UI')
  })

  it('does not offer a switch when the V2 UI is unavailable', async () => {
    uiSettings.settings = settingsWith(['v1'])

    const page = await render()

    expect(page).toContain('The V1 UI will be removed in Prefect 3.10')
    expect(page).not.toContain('Switch to V2 UI')
  })

  it('stays hidden for the rest of the browser session once dismissed', async () => {
    dismissed.value = true

    const page = await render()

    expect(page).not.toContain('The V1 UI will be removed')
  })
})
