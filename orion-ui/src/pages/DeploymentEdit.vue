<template>
  <p-layout-default class="deployment-edit">
    <template #header>
      <PageHeadingDeploymentEdit v-if="deployment" :deployment="deployment" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingDeploymentEdit } from '@prefecthq/orion-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const deploymentId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }

  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)
</script>

