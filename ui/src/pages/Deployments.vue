<template>
  <p-layout-default class="deployments">
    <template #header>
      <PageHeadingDeployments />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <DeploymentsPageEmptyState />
      </template>

      <template v-else>
        <DeploymentList @delete="deploymentsCountSubscription.refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { DeploymentList, PageHeadingDeployments, DeploymentsPageEmptyState, useWorkspaceApi } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const subscriptionOptions = {
    interval: 30000,
  }

  const deploymentsCountSubscription = useSubscription(api.deployments.getDeploymentsCount, [{}], subscriptionOptions)
  const deploymentsCount = computed(() => deploymentsCountSubscription.response ?? 0)
  const empty = computed(() => deploymentsCountSubscription.executed && deploymentsCount.value === 0)
  const loaded = computed(() => deploymentsCountSubscription.executed)

  usePageTitle('Deployments')
</script>