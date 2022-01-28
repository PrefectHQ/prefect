<template>
  <div class="main-grid">
    <m-card class="details" shadow="sm">
      <div class="d-flex align-center justify-space-between py-1 px-2">
        <!-- TODO; This card is overflowing boundaries and text truncation doesn't seem to be working... fix that or whatever. -->
        <div class="d-inline-flex flex-column">
          <div class="flex-grow-0 flex-shrink-1">
            <span class="d-inline-flex align-center text-truncate">
              <StateLabel :name="state.name" :type="state.type" class="mr-1" />
              <m-tags :tags="tags" class="mr-1 caption" />
              <div
                class="
                  caption
                  font--primary font-weight-semibold
                  text--grey-40
                  d-flex
                  text-truncate
                "
              >
                <span v-if="flowRun.start_time">
                  Started:
                  <span class="text--grey-80 mr-1 ml--half">
                    {{ formatDateTimeNumeric(flowRun.start_time) }}
                  </span>
                </span>

                <span v-if="flowRun.end_time">
                  Ended:
                  <span class="text--grey-80 mr-1 ml--half">
                    {{ formatDateTimeNumeric(flowRun.end_time) }}
                  </span>
                </span>
              </div>
            </span>
          </div>

          <div
            class="
              caption
              font--primary font-weight-semibold
              text--grey-40
              mt-1
              d-flex
              text-truncate
            "
          >
            <span v-if="deployment.name">
              Deployment:
              <span class="text--grey-80 mr-1 ml--half">
                {{ deployment.name }}
              </span>
            </span>

            <span v-if="parentFlow.name">
              Parent:
              <span class="text--grey-80">
                {{ parentFlow.name }}
              </span>
              /<router-link
                :to="`/flow-run/${parentFlowRun.id}`"
                class="mr-1 ml--half text--primary"
              >
                {{ parentFlowRun.name }}
              </router-link>
            </span>

            <span v-if="location">
              Results:
              <span class="text--grey-80 mr-1 ml--half">
                {{ location }}
              </span>
            </span>

            <span v-if="flowRun.flow_version">
              Flow version:
              <span class="text--grey-80 mr-1 ml--half">
                {{ flowRun.flow_version }}
              </span>
            </span>
          </div>
        </div>

        <div class="font--secondary">
          {{ duration }}
        </div>
      </div>
    </m-card>

    <m-card class="timeline d-flex flex-column" width="auto" shadow="sm">
      <template v-slot:header>
        <div class="d-flex align-center justify-space-between py-1 px-2">
          <div class="subheader">Timeline</div>

          <router-link :to="`/flow-run/${id}/timeline`">
            <m-icon-button icon="pi-full-screen" />
          </router-link>
        </div>
      </template>

      <div class="timeline-content pb-2 px-2 d-flex flex-grow-1">
        <Timeline
          v-if="taskRuns.length"
          :items="taskRuns"
          :max-end-time="end"
          hide-header
          axis-position="bottom"
          background-color="blue-5"
        />
      </div>
    </m-card>

    <m-card class="radar" shadow="sm">
      <template v-slot:header>
        <div class="d-flex align-center justify-space-between py-1 px-2">
          <div class="subheader">Radar</div>

          <router-link :to="`/flow-run/${id}/radar`">
            <m-icon-button icon="pi-full-screen" />
          </router-link>
        </div>
      </template>

      <div class="radar-content pb-2 px-2 d-flex flex-grow-1">
        <MiniRadarView :id="id" />
      </div>
    </m-card>
  </div>

  <ResultsListTabs v-model:tab="resultsTab" :tabs="tabs" class="mt-3" />

  <template v-if="resultsCount.value > 0">
    <div class="font--secondary caption my-2" style="min-height: 17px">
      <span>
        {{ resultsCount.value.toLocaleString() }}
        {{ toPluralString('Result', resultsCount) }}
      </span>
    </div>
  </template>

  <section
    class="results-section d-flex flex-column align-stretch justify-stretch"
  >
    <transition name="tab-fade" mode="out-in" css>
      <div
        v-if="resultsCount.value === 0"
        class="text-center my-8"
        key="no-results"
      >
        <h2> No Results Found </h2>
      </div>

      <ResultsList
        v-else-if="resultsTab == 'task_runs'"
        key="task_runs"
        :filter="taskRunsFilter"
        component="ListItemTaskRun"
        endpoint="task_runs"
        :poll-interval="5000"
      />

      <ResultsList
        v-else-if="resultsTab == 'sub_flow_runs'"
        key="sub_flow_runs"
        :filter="subFlowRunsFilter"
        component="ListItemSubFlowRun"
        endpoint="task_runs"
        :poll-interval="5000"
      />

      <template v-else-if="resultsTab == 'logs'">
        <FlowRunLogsTabContent :flow-run-id="id" :running="running" />
      </template>
    </transition>
  </section>

  <hr class="results-hr mt-3" />
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints } from '@/plugins/api'
import { State, FlowRun, Deployment, TaskRun, Flow } from '@/typings/objects'
import { computed, onBeforeUnmount, ref, Ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { secondsToApproximateString } from '@/util/util'
import { formatDateTimeNumeric } from '@/utilities/dates'
import Timeline from '@/components/Timeline/Timeline.vue'
import MiniRadarView from './MiniRadar.vue'
import StateLabel from '@/components/Global/StateLabel/StateLabel.vue'
import type { UnionFilters, FlowsFilter } from '@prefecthq/orion-design'
import { ResultsListTabs, ResultsListTab } from '@prefecthq/orion-design'
import FlowRunLogsTabContent from '@/components/FlowRunLogsTabContent.vue'
import { toPluralString } from '@/utilities/strings'

const route = useRoute()

const resultsTab: Ref<'task_runs' | 'sub_flow_runs' | 'logs'> = ref('task_runs')

const id = ref(route?.params.id as string)

const flowRunBaseFilter = computed(() => {
  return { id: id.value }
})

const flowRunBase: Query = await Api.query({
  endpoint: Endpoints.flow_run,
  body: flowRunBaseFilter,
  options: {
    pollInterval: 5000
  }
}).fetch()

const flowId = computed<string>(() => {
  return flowRunBase.response.value.flow_id
})

const parentTaskRunId = computed<string>(() => {
  return flowRunBase.response.value.parent_task_run_id
})

const deploymentId = computed<string>(() => {
  return flowRunBase.response.value.deployment_id
})

const flowFilter = computed(() => {
  return {
    id: flowId.value
  }
})

const deploymentFilter = computed(() => {
  return {
    id: deploymentId.value
  }
})

const parentFlowFilter = computed<FlowsFilter>(() => {
  return {
    task_runs: {
      id: {
        any_: [parentTaskRunId.value]
      }
    }
  }
})

const taskRunsFilter = computed<UnionFilters>(() => {
  return {
    flow_runs: {
      id: {
        any_: [id.value]
      }
    }
  }
})

const subFlowRunsFilter = computed<UnionFilters>(() => {
  return {
    flow_runs: {
      id: {
        any_: [id.value]
      }
    },
    task_runs: {
      subflow_runs: {
        exists_: true
      }
    }
  }
})

const queries: { [key: string]: Query } = {
  flow: Api.query({
    endpoint: Endpoints.flow,
    body: flowFilter
  }),
  deployment: Api.query({
    endpoint: Endpoints.deployment,
    body: deploymentFilter,
    options: {
      paused: !deploymentId.value
    }
  }),
  parent_flow: Api.query({
    endpoint: Endpoints.flows,
    body: parentFlowFilter,
    options: {
      paused: !parentTaskRunId.value
    }
  }),
  parent_flow_run: Api.query({
    endpoint: Endpoints.flow_runs,
    body: parentFlowFilter,
    options: {
      paused: !parentTaskRunId.value
    }
  }),
  task_runs_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: taskRunsFilter,
    options: {
      pollInterval: 10000
    }
  }),
  task_runs: Api.query({
    endpoint: Endpoints.task_runs,
    body: taskRunsFilter,
    options: {
      pollInterval: 10000
    }
  }),
  sub_flow_runs_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: subFlowRunsFilter,
    options: {
      pollInterval: 10000
    }
  })
}

const countMap = {
  task_runs: 'task_runs_count',
  sub_flow_runs: 'sub_flow_runs_count',
  logs: '' // dummy because there is no count query for logs. And not taking the time to refactor results count right now
}

const resultsCount = computed(() => {
  if (!resultsTab.value) return 0
  return queries[countMap[resultsTab.value]]?.response || 0
})

const deployment = computed<Deployment>(() => {
  return queries.deployment.response?.value || {}
})

const parentFlow = computed<Flow>(() => {
  return queries.parent_flow.response?.value?.[0] || {}
})

const parentFlowRun = computed<FlowRun>(() => {
  return queries.parent_flow_run.response?.value?.[0] || {}
})

const location = computed(() => {
  return deployment.value?.flow_data?.blob
})

const flowRun = computed<FlowRun>(() => {
  return flowRunBase.response?.value || {}
})

const end = computed<string>(() => {
  return flowRun.value.end_time
})

const state = computed<State>(() => {
  return flowRun.value?.state
})

const running = computed<boolean>(() => {
  return state.value.type == 'RUNNING'
})

const tags = computed(() => {
  return flowRun.value?.tags || []
})

const taskRunsCount = computed(() => {
  return queries.task_runs_count.response?.value || 0
})

const subFlowRunsCount = computed(() => {
  return queries.sub_flow_runs_count.response?.value || 0
})

const taskRuns = computed<TaskRun[]>(() => {
  return queries.task_runs.response?.value || []
})

const tabs = computed<ResultsListTab[]>(() => [
  {
    label: 'Task Runs',
    href: 'task_runs',
    count: taskRunsCount.value,
    icon: 'pi-task'
  },
  {
    label: 'Subflow Runs',
    href: 'sub_flow_runs',
    count: subFlowRunsCount.value,
    icon: 'pi-flow-run'
  },
  {
    label: 'Logs',
    href: 'logs',
    icon: 'pi-logs-fill'
  }
])

const duration = computed(() => {
  return state.value.type == 'PENDING' || state.value.type == 'SCHEDULED'
    ? '--'
    : flowRun.value.total_run_time
    ? secondsToApproximateString(flowRun.value.total_run_time)
    : secondsToApproximateString(flowRun.value.estimated_run_time)
})

// This cleanup is necessary since the initial flow run query isn't
// wrapped in the queries object
onBeforeUnmount(() => {
  flowRunBase.stopPolling()
  Api.queries.delete(flowRunBase.id)
})

const idWatcher = watch(route, () => {
  id.value = route?.params.id as string
})

onBeforeRouteLeave(() => {
  idWatcher()
})

watch(id, async () => {
  if (!id.value) return

  await flowRunBase.fetch()
  queries.flow.fetch()

  queries.task_runs_count.fetch()
  queries.task_runs.fetch()
  queries.sub_flow_runs_count.fetch()

  if (deploymentId.value) queries.deployment.fetch()
  else queries.deployment.clearResult()
  if (parentTaskRunId.value) queries.parent_flow.fetch()
  else queries.parent_flow.clearResult()
  if (parentTaskRunId.value) queries.parent_flow_run.fetch()
  else queries.parent_flow_run.clearResult()

  resultsTab.value = 'task_runs'
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/index.scss';
</style>
