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
      <template #header>
        <div class="d-flex align-center justify-space-between py-1 px-2">
          <div class="subheader">
            Timeline
          </div>

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
      <template #header>
        <div class="d-flex align-center justify-space-between py-1 px-2">
          <div class="subheader">
            Radar
          </div>

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

  <ListTabSet v-model:value="resultsTab" :tabs="tabs" class="mt-3">
    <template #logs>
      <section class="flow-run__tab-content">
        <FlowRunLogsTabContent :flow-run-id="id" :running="running" />
      </section>
    </template>

    <template #task_runs="{ tab }">
      <section class="results-section">
        <ResultsList
          v-if="tab.count > 0"
          key="task_runs"
          :filter="taskRunsFilter"
          component="ListItemTaskRun"
          endpoint="task_runs"
          :poll-interval="5000"
        />
        <div v-else class="text-center my-8">
          <h2>No results found</h2>
        </div>
      </section>
    </template>

    <template #sub_flow_runs="{ tab }">
      <section class="results-section">
        <ResultsList
          v-if="tab.count > 0"
          key="sub_flow_runs"
          :filter="subFlowRunsFilter"
          component="ListItemSubFlowRun"
          endpoint="task_runs"
          :poll-interval="5000"
        />
        <div v-else class="text-center my-8">
          <h2>No results found</h2>
        </div>
      </section>
    </template>
  </ListTabSet>

  <hr class="results-hr mt-3">
</template>

<script lang="ts" setup>
  import { UnionFilters, ListTabSet, ListTab, States } from '@prefecthq/orion-design'
  import { computed, onBeforeUnmount, ref, Ref, watch } from 'vue'
  import { useRoute, onBeforeRouteLeave } from 'vue-router'
  import MiniRadarView from './MiniRadar.vue'
  import FlowRunLogsTabContent from '@/components/FlowRunLogsTabContent.vue'
  import StateLabel from '@/components/Global/StateLabel/StateLabel.vue'
  import Timeline from '@/components/Timeline/Timeline.vue'
  import { Api, Query, Endpoints } from '@/plugins/api'
  import { State, FlowRun, Deployment, TaskRun, Flow } from '@/typings/objects'
  import { secondsToApproximateString } from '@/util/util'
  import { formatDateTimeNumeric } from '@/utilities/dates'

  const route = useRoute()

  type Tab = 'task_runs' | 'sub_flow_runs' | 'logs'
  const resultsTab: Ref<Tab> = ref('logs')

  const id = ref(route?.params.id as string)

  const flowRunBaseFilter = computed(() => {
    return { id: id.value }
  })

  const flowRunBase: Query = await Api.query({
    endpoint: Endpoints.flow_run,
    body: flowRunBaseFilter,
    options: {
      pollInterval: 5000,
    },
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
      id: flowId.value,
    }
  })

  const deploymentFilter = computed(() => {
    return {
      id: deploymentId.value,
    }
  })

  const parentFlowFilter = computed(() => {
    return {
      task_runs: {
        id: {
          any_: [parentTaskRunId.value],
        },
      },
    }
  })

  const taskRunsFilter = computed<UnionFilters>(() => {
    return {
      flow_runs: {
        id: {
          any_: [id.value],
        },
      },
    }
  })

  const subFlowRunsFilter = computed<UnionFilters>(() => {
    return {
      flow_runs: {
        id: {
          any_: [id.value],
        },
      },
      task_runs: {
        subflow_runs: {
          exists_: true,
        },
      },
    }
  })

  const queries: Record<string, Query> = {
    flow: Api.query({
      endpoint: Endpoints.flow,
      body: flowFilter,
    }),
    deployment: Api.query({
      endpoint: Endpoints.deployment,
      body: deploymentFilter,
      options: {
        paused: !deploymentId.value,
      },
    }),
    parent_flow: Api.query({
      endpoint: Endpoints.flows,
      body: parentFlowFilter,
      options: {
        paused: !parentTaskRunId.value,
      },
    }),
    parent_flow_run: Api.query({
      endpoint: Endpoints.flow_runs,
      body: parentFlowFilter,
      options: {
        paused: !parentTaskRunId.value,
      },
    }),
    task_runs_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: taskRunsFilter,
      options: {
        pollInterval: 10000,
      },
    }),
    task_runs: Api.query({
      endpoint: Endpoints.task_runs,
      body: taskRunsFilter,
      options: {
        pollInterval: 10000,
      },
    }),
    sub_flow_runs_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: subFlowRunsFilter,
      options: {
        pollInterval: 10000,
      },
    }),
  }

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
    return state.value.type == States.RUNNING
  })

  const tags = computed(() => {
    return flowRun.value?.tags || []
  })

  const taskRuns = computed<TaskRun[]>(() => {
    return queries.task_runs.response?.value || []
  })

  const tabs = computed<ListTab[]>(() => [
    {
      title: 'Logs',
      key: 'logs',
      icon: 'pi-logs-fill',
      count: null,
    },
    {
      title: 'Task Runs',
      key: 'task_runs',
      icon: 'pi-task',
      count: queries.task_runs_count.response?.value ?? 0,
    },
    {
      title: 'Subflow Runs',
      key: 'sub_flow_runs',
      icon: 'pi-flow-run',
      count: queries.sub_flow_runs_count.response?.value ?? 0,
    },
  ])

  const duration = computed(() => {
    if (state.value.type == 'PENDING' || state.value.type == 'SCHEDULED') {
      return '--'
    }

    if (flowRun.value.total_run_time) {
      return secondsToApproximateString(flowRun.value.total_run_time)
    }

    return secondsToApproximateString(flowRun.value.estimated_run_time)
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
    if (!id.value) {
      return
    }

    await flowRunBase.fetch()
    queries.flow.fetch()

    queries.task_runs_count.fetch()
    queries.task_runs.fetch()
    queries.sub_flow_runs_count.fetch()

    if (deploymentId.value) {
      queries.deployment.fetch()
    } else {
      queries.deployment.clearResult()
    }
    if (parentTaskRunId.value) {
      queries.parent_flow.fetch()
    } else {
      queries.parent_flow.clearResult()
    }
    if (parentTaskRunId.value) {
      queries.parent_flow_run.fetch()
    } else {
      queries.parent_flow_run.clearResult()
    }

    resultsTab.value = 'task_runs'
  })
</script>

<style lang="scss">
@use '@/styles/views/flow-run/index.scss';

.results-section {
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  flex-direction: column;
}
</style>