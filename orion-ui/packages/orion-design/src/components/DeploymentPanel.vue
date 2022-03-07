<template>
  <m-panel class="deployment-panel">
    <template #title>
      <div class="deployment-panel__title">
        <i class="pi pi-map-pin-line pi-sm deployment-panel__icon" />
        <span class="ml-1">{{ deployment.name }}</span>
      </div>
    </template>

    <div class="deployment-panel__details">
      <DetailsKeyValue label="Created Date" :value="formatDateTimeNumeric(deployment.created)" stacked />
      <DetailsKeyValue label="Schedule" :value="schedule" stacked />
      <DetailsKeyValue label="Flow storage type" :value="deployment.flowData.encoding" stacked />
      <DetailsKeyValue label="Flow runner" :value="deployment.flowRunner?.type" stacked />
      <DetailsKeyValue label="Tags" stacked>
        <m-tags :tags="deployment.tags" />
      </DetailsKeyValue>
      <RecentFlowRunsPanelSection v-bind="{ baseFilter, dashboardRoute, getFlowRunsCount }" />
      <DeploymentParametersPanelSection
        :parameters="{
          test: 'hello world',
        }"
      />
    </div>

    <template #actions="{ close }">
      <m-button @click="close">
        Close
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { RouteLocationRaw } from 'vue-router'
  import DeploymentParametersPanelSection from './DeploymentParametersPanelSection.vue'
  import DetailsKeyValue from './DetailsKeyValue.vue'
  import RecentFlowRunsPanelSection from './RecentFlowRunsPanelSection.vue'
  import { Deployment } from '@/models/Deployment'
  import { CronSchedule, IntervalSchedule, RRuleSchedule } from '@/models/Schedule'
  import { FlowRunsApi } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'
  import { formatDateTimeNumeric } from '@/utilities/dates'
  import { secondsToApproximateString } from '@/utilities/seconds'

  const props = defineProps<{
    deployment: Deployment,
    getFlowRunsCount: FlowRunsApi['getFlowRunsCount'],
    dashboardRoute: Exclude<RouteLocationRaw, string>,
  }>()

  console.log(props.deployment)

  const baseFilter = computed<Required<Filter>>(() => ({
    object: 'deployment',
    property: 'name',
    type: 'string',
    operation: 'equals',
    value: props.deployment.name,
  }))

  const schedule = computed(() => {
    const { schedule } = props.deployment

    if (schedule instanceof IntervalSchedule) {
      return `Every ${secondsToApproximateString(schedule.interval)}`
    }

    if (schedule instanceof CronSchedule) {
      return schedule.cron
    }

    if (schedule instanceof RRuleSchedule) {
      return schedule.rrule
    }

    return null
  })
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
</style>