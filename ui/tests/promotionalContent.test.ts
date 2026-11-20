import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ApiStatusToast from '@/components/ApiStatusToast.vue'
import ContextSidebar from '@/components/ContextSidebar.vue'
import Dashboard from '@/pages/Dashboard.vue'
import { SlotContainer } from 'tests/SlotContainer'

const { getSettings } = vi.hoisted(() => ({ getSettings: vi.fn() }))

vi.mock('@/compositions/usePrefectApi', () => ({
  usePrefectApi: () => ({ admin: { getSettings } }),
}))
vi.mock('@/compositions/useCan', () => ({ useCan: () => ({ read: { 'work_pool': true } }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ path: '/' }) }))
vi.mock('@/router', () => ({ routes: new Proxy({}, { get: () => () => '/' }) }))
vi.mock('@/services/uiSettings', () => ({
  UiSettings: { settings: null, loadOptional: () => Promise.resolve(null) },
}))
vi.mock('@/utilities/uiVersion', () => ({
  V2_PROMO_DISMISSED_STORAGE_KEY: 'v2-promo-dismissed',
  isUiAvailable: () => false,
  switchToV2Ui: vi.fn(),
}))
vi.mock('@/components/JoinTheCommunityModal.vue', () => ({ default: { render: () => null } }))
vi.mock('@prefecthq/prefect-design', async () => {
  const { SlotContainer: Container } = await import('tests/SlotContainer')
  return { PContextSidebar: Container, PContextNavItem: Container, PButton: Container, PHeading: Container }
})
vi.mock('@prefecthq/vue-compositions', async () => {
  const { ref } = await import('vue')
  return {
    useStorage: (_location: string, _key: string, fallback: boolean) => ({ value: ref(fallback) }),
    useSubscription: () => ({ executed: true, response: 0 }),
  }
})
vi.mock('@prefecthq/prefect-ui-library', async () => {
  const { ref } = await import('vue')
  const { SlotContainer: Container } = await import('tests/SlotContainer')
  return {
    ...Object.fromEntries([
      'DashboardWorkPoolsCard', 'WorkspaceDashboardFlowRunsCard', 'CumulativeTaskRunsCard',
      'PageHeading', 'FlowRunTagsInput', 'FlowRunsPageEmptyState', 'MarketingBanner', 'DateRangeSelect',
    ].map(name => [name, Container])),
    localization: { info: { variables: 'Variables' } },
    useShowModal: () => ({ showModal: ref(false), open: vi.fn() }),
    useWorkspaceApi: () => ({ flowRuns: { getFlowRunsCount: vi.fn() } }),
    subscriptionIntervalKey: Symbol('subscriptionInterval'),
    dateFunctions: { secondsToMilliseconds: (seconds: number) => seconds * 1000 },
    secondsInDay: 86400,
    useWorkspaceDashboardFilterFromRoute: () => ({ hideSubflows: false, tags: [], range: {} }),
    mapper: { map: vi.fn() },
  }
})

async function render(component: typeof ContextSidebar): Promise<string> {
  const app = createSSRApp(component)
  for (const name of ['PLayoutDefault', 'PButton', 'PIcon', 'RouterLink']) {
    app.component(name, SlotContainer)
  }
  return await renderToString(app)
}

beforeEach(() => {
  vi.clearAllMocks()
  // Reproduce the stale value cached by the old flat-key lookup.
  const values = new Map([['prefect-show-promotional-content', 'undefined']])
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, String(value)),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

for (const [name, component, promotion] of [
  ['sidebar', ContextSidebar, 'Ready to scale?'],
  ['dashboard', Dashboard, 'Upgrade to Cloud'],
] as const) {
  describe(name, () => {
    it.each([false, true])('honors the nested promotional setting %s through the error toast', async enabled => {
      getSettings.mockResolvedValue({ server: { ui: { 'show_promotional_content': enabled } } })

      const page = await render(component)
      expect(getSettings).toHaveBeenCalledOnce()
      expect(page.includes(promotion)).toBe(enabled)
      expect(localStorage.getItem('prefect-show-promotional-content')).toBe(String(enabled))

      // The API error interceptor creates this toast after a subsequent request fails.
      const toast = await render(ApiStatusToast)
      expect(toast.includes('You can use Prefect Cloud for free, anytime.')).toBe(enabled)
      expect(toast.includes('Please check your connection and try again.')).toBe(!enabled)
    })
  })
}
