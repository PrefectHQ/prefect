<template>
  <p-layout-well class="concurrencyLimit">
    <template #header>
      <PageHeadingConcurrencyLimit v-if="concurrencyLimit" :concurrency-limit="concurrencyLimit" @delete="deleteConcurrencyLimit" />
    </template>

    <p-tabs v-model:selected="tab" :tabs="tabs">
      <template #details>
        <ConcurrencyLimitDetails v-if="concurrencyLimit" :concurrency-limit="concurrencyLimit" />
      </template>
      <template #active-task-runs>
        <ConcurrencyLimitActiveRuns v-if="concurrencyLimit?.activeSlots" :active-slots="concurrencyLimit.activeSlots" />
      </template>
    </p-tabs>

    <template #well>
      <ConcurrencyLimitDetails v-if="concurrencyLimit" alternate :concurrency-limit="concurrencyLimit" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { PageHeadingConcurrencyLimit, ConcurrencyLimitDetails, ConcurrencyLimitActiveRuns, useTabs, useWorkspaceApi } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const api = useWorkspaceApi()
  const concurrencyLimitId = useRouteParam('concurrencyLimitId')
  const router = useRouter()

  const computedTabs = computed(() => [
    { label: 'Details', hidden: media.xl },
    { label: 'Active Task Runs' },
  ])
  const tab = useRouteQueryParam('tab', 'Details')
  const { tabs } = useTabs(computedTabs, tab)

  const subscriptionOptions = {
    interval: 300000,
  }

  const concurrencyLimitSubscription = useSubscription(api.concurrencyLimits.getConcurrencyLimit, [concurrencyLimitId.value], subscriptionOptions)
  const concurrencyLimit = computed(() => concurrencyLimitSubscription.response)


  function deleteConcurrencyLimit(): void {
    router.push(routes.concurrencyLimits())
  }

  const title = computed<string>(() => {
    if (!concurrencyLimit.value) {
      return 'Concurrency Limit'
    }

    return `Concurrency Limit: ${concurrencyLimit.value.tag}`
  })

  usePageTitle(title)
</script>