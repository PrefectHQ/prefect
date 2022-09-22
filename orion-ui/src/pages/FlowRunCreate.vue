<template>
  <p-layout-default v-if="deployment">
    <template #header>
      <PageHeadingFlowRunCreate :deployment="deployment" />
    </template>

    <FlowRunCreateForm :deployment="deployment" @submit="createFlowRun" @cancel="goBack" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { FlowRunCreateForm, PageHeadingFlowRunCreate, DeploymentFlowRunCreate, ToastFlowRunCreate } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, h } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const deploymentId = useRouteParam('id')
  const router = useRouter()

  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId])
  const deployment = computed(() => deploymentSubscription.response)

  const createFlowRun = async (deploymentFlowRun: DeploymentFlowRunCreate): Promise<void> => {
    try {
      const flowRun = await deploymentsApi.createDeploymentFlowRun(deploymentId.value, deploymentFlowRun)
      const startTime = deploymentFlowRun.state?.stateDetails?.scheduledTime ?? undefined
      const immediate = !startTime
      const toastMessage = h(ToastFlowRunCreate, { flowRun, flowRunRoute: routes.flowRun, router, immediate, startTime })
      showToast(toastMessage, 'success')
      router.push(routes.deployment(deploymentId.value))
    } catch (error) {
      showToast('Something went wrong trying to create a flow run', 'error')
      console.error(error)
    }
  }

  const goBack = (): void => {
    router.back()
  }

  const title = computed<string>(() => {
    if (!deployment.value) {
      return 'Create Flow Run for Deployment'
    }
    return `Create Flow Run for Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)
</script>