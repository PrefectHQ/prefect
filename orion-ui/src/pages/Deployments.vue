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
        <DeploymentsTable :deployments="deployments" @delete="deploymentsSubscription.refresh()" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { DeploymentsTable, PageHeadingDeployments, DeploymentsPageEmptyState, mocker } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const deploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [{}], subscriptionOptions)
  const deployments = computed(() => mocker.createMany('deployment', 10))
  const empty = computed(() => deploymentsSubscription.executed && deployments.value.length === 0)
  const loaded = computed(() => deploymentsSubscription.executed)
</script>