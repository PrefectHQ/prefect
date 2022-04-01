<template>
  <m-panel class="deployment-panel">
    <template #title>
      <div class="deployment-panel__title">
        <i class="pi pi-map-pin-line pi-sm deployment-panel__icon" />
        <span class="ml-1">{{ deployment.name }}</span>
      </div>
    </template>

    <m-loader :loading="saving" class="deployment-panel__loader" />

    <div class="deployment-panel__details">
      <DetailsKeyValue label="Created Date" :value="formatDateTimeNumericInTimeZone(deployment.created)" stacked />
      <DetailsKeyValue label="Schedule" :value="schedule" stacked />
      <DetailsKeyValue label="Flow storage type" :value="deployment.flowData.encoding" stacked />
      <DetailsKeyValue label="Storage Details" :value="blob.data" stacked />
      <DetailsKeyValue label="Block ID" :value="blob.block_id" stacked />
      <DetailsKeyValue label="Flow runner" :value="deployment.flowRunner?.type" stacked />
      <DetailsKeyValue label="Tags" stacked>
        <m-tags :tags="deployment.tags" />
      </DetailsKeyValue>
      <RecentFlowRunsPanelSection v-bind="{ baseFilter, dashboardRoute, flowRunsApi }" />
      <DeploymentParametersPanelSection :parameters="deployment.parameters" />
      <DeleteSection label="Deployment" @remove="remove" />
    </div>

    <template #actions="{ close }">
      <m-button @click="close">
        Close
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import { RouteLocationRaw } from 'vue-router'
  import DeleteSection from '@/components/DeleteSection.vue'
  import DeploymentParametersPanelSection from '@/components/DeploymentParametersPanelSection.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import RecentFlowRunsPanelSection from '@/components/RecentFlowRunsPanelSection.vue'
  import { Deployment } from '@/models/Deployment'
  import { CronSchedule, IntervalSchedule, RRuleSchedule } from '@/models/Schedule'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { FlowRunsApi } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'
  import { formatDateTimeNumericInTimeZone } from '@/utilities/dates'
  import { exitPanel } from '@/utilities/panels'
  import { secondsToString } from '@/utilities/seconds'
  import { FlowsListSubscription, DeploymentsListSubscription } from '@/utilities/subscriptions'
  import { showToast } from '@/utilities/toasts'


  const props = defineProps<{
    deployment: Deployment,
    flowsListSubscription?: FlowsListSubscription,
    deploymentsListSubscription?: DeploymentsListSubscription,
    deploymentsApi: DeploymentsApi,
    flowRunsApi: FlowRunsApi,
    dashboardRoute: Exclude<RouteLocationRaw, string>,
  }>()


  const baseFilter = computed<Required<Filter>>(() => ({
    object: 'deployment',
    property: 'name',
    type: 'string',
    operation: 'equals',
    value: props.deployment.name,
  }))

  const blob = computed(()=>JSON.parse(props.deployment.flowData.blob))
  const saving = ref(false)

  const schedule = computed(() => {
    const { schedule } = props.deployment

    if (schedule instanceof IntervalSchedule) {
      return `Every ${secondsToString(schedule.interval)}`
    }

    if (schedule instanceof CronSchedule) {
      return schedule.cron
    }

    if (schedule instanceof RRuleSchedule) {
      return schedule.rrule
    }

    return null
  })


  async function remove(): Promise<void> {
    try {
      saving.value = true
      await props.deploymentsApi.deleteDeployment(props.deployment.id)
      showToast('Deleted Deployment', 'success')

      if (props.flowsListSubscription) {
        props.flowsListSubscription.refresh()
      }
      if (props.deploymentsListSubscription) {
        props.deploymentsListSubscription.refresh()
      }
      exitPanel()
    } catch (err) {
      console.warn('error deleting deployment', err)
      showToast('Error deleting deployment', 'error')
    } finally {
      saving.value = false
    }
  }
</script>

<style lang="scss">
.deployment-panel__title {
  display: flex;
  align-items: center;
}

.deployment-panel__icon {
  position: relative;
  top: 0.05em;
  color: var(--grey-40);
}

.deployment-panel__details {
  display: grid;
  gap: var(--m-2);
}

.deployment-panel__id {
  display: flex;
  justify-content: space-between;
  min-width: 0;
}

.deployment-panel__count {
  font-weight: 400;
  font-family: var(--font-secondary);
  font-size: 13px;
  letter-spacing: -0.09px;
  line-height: 18px;
  text-align: center;
  color: var(--grey-80);
  border: 1px solid var(--secondary-hover);
  border-radius: 100px;
  min-width: 24px;
  display: inline-block;
}

.deployment-panel__loader {
  position: absolute !important;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>