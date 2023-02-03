<template>
  <p-layout-default v-if="deployment">
    <template #header>
      <PageHeadingFlowRunCreate :deployment="deployment" />
    </template>

    <FlowRunCreateForm :deployment="deployment" :flow-run="flowRun" @submit="createFlowRun" @cancel="goBack" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { FlowRunCreateForm, PageHeadingFlowRunCreate, DeploymentFlowRunCreate, ToastFlowRunCreate, useWorkspaceApi } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscriptionWithDependencies, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, h } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const api = useWorkspaceApi()
  const deploymentId = useRouteParam('deploymentId')
  const flowRunId = useRouteParam('flowRunId')
  const router = useRouter()

  const flowRunArgs = computed<[string] | null>(() => {
    if (!flowRunId.value) {
      return null
    }

    return [flowRunId.value]
  })

  const flowRunSubscription = useSubscriptionWithDependencies(api.flowRuns.getFlowRun, flowRunArgs)
  const flowRun = computed(() => flowRunSubscription.response)

  const deploymentArgs = computed<[string] | null>(() => {
    if (flowRun.value?.deploymentId) {
      return [flowRun.value.deploymentId]
    }

    if (deploymentId.value) {
      return [deploymentId.value]
    }

    return null
  })

  const deploymentSubscription = useSubscriptionWithDependencies(api.deployments.getDeployment, deploymentArgs)
  const deployment = computed(() => deploymentSubscription.response)

  const createFlowRun = async (deploymentFlowRun: DeploymentFlowRunCreate): Promise<void> => {
    try {
      const deploymentId = computed(() => deployment.value!.id)
      const flowRun = await api.deployments.createDeploymentFlowRun(deploymentId.value, deploymentFlowRun)
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