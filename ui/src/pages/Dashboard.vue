<template>
  <p-layout-default class="workspace-dashboard">
    <template #header>
      <PageHeading :crumbs="crumbs" class="workspace-dashboard__page-heading">
        <template v-if="loaded && !empty" #actions>
          <div class="workspace-dashboard__header-actions">
            <div class="workspace-dashboard__subflows-toggle">
              <p-toggle v-model="filter.hideSubflows" append="Hide subflows" />
            </div>
            <FlowRunTagsInput v-model:selected="filter.tags" empty-message="All tags" />
            <DateRangeSelect v-model="filter.range" class="workspace-dashboard__date-select" />
          </div>
        </template>
      </PageHeading>
    </template>
    <div v-if="showTryNewUiBanner" class="workspace-dashboard__ui-switch-banner">
      <div class="workspace-dashboard__ui-switch-content">
        <div class="workspace-dashboard__ui-switch-copy">
          <p class="workspace-dashboard__ui-switch-eyebrow">
            Preview available
          </p>
          <p class="workspace-dashboard__ui-switch-title">
            Try the new UI
          </p>
          <p class="workspace-dashboard__ui-switch-description">
            Explore the redesigned Prefect experience in this browser. You can switch back at any time.
          </p>
        </div>
        <div class="workspace-dashboard__ui-switch-actions">
          <p-button small @click="dismissTryNewUiBanner">
            Not now
          </p-button>
          <p-button primary @click="switchToV2">
            Try the new UI
          </p-button>
        </div>
      </div>
    </div>
    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <div class="workspace-dashboard__grid">
          <WorkspaceDashboardFlowRunsCard :filter="filter" />
          <div class="workspace-dashboard__side">
            <CumulativeTaskRunsCard :filter="tasksFilter" />
            <DashboardWorkPoolsCard class="workspace-dashboard__work-pools" :filter="filter" />
          </div>
        </div>
      </template>
    </template>
    <MarketingBanner
      v-if="showPromotionalContent"
      title="Ready to scale?"
      subtitle="Webhooks, role and object-level security, and serverless push work pools on Prefect Cloud"
    >
      <template #actions>
        <p-button to="https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss&utm_term=none&utm_content=none" target="_blank" primary>
          Upgrade to Cloud
        </p-button>
      </template>
    </MarketingBanner>
  </p-layout-default>
</template>

<script setup lang="ts">
  import { Crumb } from '@prefecthq/prefect-design'
  import {
    DashboardWorkPoolsCard,
    WorkspaceDashboardFlowRunsCard,
    CumulativeTaskRunsCard,
    PageHeading,
    FlowRunTagsInput,
    FlowRunsPageEmptyState,
    useWorkspaceApi,
    subscriptionIntervalKey,
    mapper,
    TaskRunsFilter,
    MarketingBanner,
    Getter,
    DateRangeSelect,
    useWorkspaceDashboardFilterFromRoute,
    dateFunctions,
    secondsInDay
  } from '@prefecthq/prefect-ui-library'
  import { useStorage, useSubscription } from '@prefecthq/vue-compositions'
  import { computed, provide, ref } from 'vue'
  import { useRoute } from 'vue-router'
  import { usePrefectApi } from '@/compositions/usePrefectApi'
  import { Settings, UiSettings } from '@/services/uiSettings'
  import { V2_PROMO_DISMISSED_STORAGE_KEY, isUiAvailable, switchToV2Ui } from '@/utilities/uiVersion'

  provide(subscriptionIntervalKey, {
    interval: dateFunctions.secondsToMilliseconds(30),
  })

  const api = useWorkspaceApi()
  const prefectApi = usePrefectApi()
  const route = useRoute()
  const browserUiSettings = ref<Settings | null>(UiSettings.settings)
  const serverSettings = await prefectApi.admin.getSettings()
  const showPromotionalContent = computed(() => serverSettings.PREFECT_SERVER_UI_SHOW_PROMOTIONAL_CONTENT)
  const canSwitchToV2 = computed(() =>
    browserUiSettings.value !== null &&
    isUiAvailable(browserUiSettings.value, 'v2'),
  )
  const { value: tryNewUiBannerDismissed } = useStorage('local', V2_PROMO_DISMISSED_STORAGE_KEY, false)
  const showTryNewUiBanner = computed(() =>
    canSwitchToV2.value &&
    !tryNewUiBannerDismissed.value,
  )

  void UiSettings.loadOptional(route.path).then(settings => {
    browserUiSettings.value = settings
  })

  // Cache to localStorage for use in error toasts
  localStorage.setItem('prefect-show-promotional-content', String(showPromotionalContent.value))
  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)
  const crumbs: Crumb[] = [{ text: 'Dashboard' }]

  const filter = useWorkspaceDashboardFilterFromRoute({
    range: { type: 'span', seconds: -secondsInDay },
    tags: [],
  })

  const tasksFilter: Getter<TaskRunsFilter> = () => mapper.map('WorkspaceDashboardFilter', filter, 'TaskRunsFilter')

  function dismissTryNewUiBanner(): void {
    tryNewUiBannerDismissed.value = true
  }

  function switchToV2(): void {
    if (browserUiSettings.value === null) {
      return
    }

    tryNewUiBannerDismissed.value = true
    switchToV2Ui(browserUiSettings.value, route.path)
  }
</script>

<style>
.workspace-dashboard__page-heading { @apply
  grid
  md:flex
  md:flex-row
  md:items-center
  min-h-11
}

.workspace-dashboard__header-actions { @apply
  flex
  flex-col
  w-full
  max-w-full
  gap-2
  md:w-auto
  md:inline-flex
  md:flex-row
  items-center
}

.workspace-dashboard__date-select { @apply
  min-w-0
}

.workspace-dashboard__grid { @apply
  grid
  grid-cols-1
  gap-4
  items-start
  xl:grid-cols-2
}

.workspace-dashboard__side { @apply
  grid
  grid-cols-1
  gap-4
}

.workspace-dashboard__subflows-toggle { @apply
  pr-2
  w-full
  md:w-auto
}

.workspace-dashboard__ui-switch-banner { @apply
  mb-4
  rounded-xl
  border
  border-blue-300
  bg-blue-50
  px-5
  py-4
  shadow-md
}

.workspace-dashboard__ui-switch-content { @apply
  flex
  flex-col
  gap-3
  lg:flex-row
  lg:items-center
  lg:justify-between
}

.workspace-dashboard__ui-switch-copy { @apply
  flex
  flex-col
  gap-1
}

.workspace-dashboard__ui-switch-eyebrow { @apply
  text-xs
  font-semibold
  uppercase
  tracking-wide
  text-blue-700
}

.workspace-dashboard__ui-switch-title { @apply
  text-lg
  font-semibold
  text-blue-950
}

.workspace-dashboard__ui-switch-description { @apply
  text-sm
  text-blue-900
}

.workspace-dashboard__ui-switch-actions { @apply
  flex
  flex-wrap
  gap-2
  justify-end
}
</style>
