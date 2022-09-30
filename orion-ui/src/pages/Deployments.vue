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
        <DeploymentsTable :deployments="deployments" @update="deploymentsSubscription.refresh()" @delete="deploymentsSubscription.refresh()" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { DeploymentsTable, PageHeadingDeployments, DeploymentsPageEmptyState } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const deploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [{}], subscriptionOptions)
  const deployments = computed(() => deploymentsSubscription.response ?? [])
  const empty = computed(() => deploymentsSubscription.executed && deployments.value.length === 0)
  const loaded = computed(() => deploymentsSubscription.executed)

  usePageTitle('Deployments')
</script>