<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-2">
      <bread-crumbs class="flex-grow-1" :crumbs="crumbs" icon="pi-flow-run" />
      <div class="text-truncate">
        <span>
          Flow Version:
          <span class="font-weight-semibold">{{ flowRun.flow_version }}</span>
        </span>

        <a v-breakpoints="'md'" class="copy-link ml-1">
          <i class="pi pi-link pi-xs" />
          Copy Run ID
        </a>
      </div>
    </div>

    <div class="main-grid">
      <Card class="details" shadow="sm">
        <div
          class="d-flex align-center justify-space-between py-1 px-2"
          style="width: 100%; height: 100%"
        >
          <!-- TODO; This card is overflowing boundaries and text truncation doesn't seem to be working... fix that or whatever. -->
          <div class="d-inline-flex flex-column">
            <div class="flex-grow-0 flex-shrink-1">
              <span
                class="run-state correct-text caption mr-1"
                :class="state.type?.toLowerCase() + '-bg'"
              >
                {{ state.name }}
              </span>

              <span class="d-inline-flex align-center text-truncate">
                <Tag
                  v-for="tag in tags"
                  :key="tag"
                  color="secondary-pressed"
                  class="font--primary caption font-weight-semibold mr-1"
                  icon="pi-label"
                  flat
                >
                  {{ tag }}
                </Tag>
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
              <span> Deployment: </span>
              <span class="text--grey-80">
                {{ deployment.name }}
              </span>

              <span class="ml-1"> Results: </span>
              <span class="text--grey-80">
                {{ location }}
              </span>
            </div>
          </div>

          <div class="font--secondary">
            {{ duration }}
          </div>
        </div>
      </Card>
      <Card class="timeline" shadow="sm"
        >this is where the timeline should probably go</Card
      >
      <Card class="schematic" shadow="sm"
        >this is where i'd put a mini schematic... if i had one</Card
      >
    </div>

    <Tabs v-model="resultsTab" class="mt-3">
      <Tab href="task_runs" class="subheader">
        <i class="pi pi-task mr-1 text--grey-40" />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task_runs' }"
        >
          {{ taskRunsCount.toLocaleString() }}
        </span>
      </Tab>

      <Tab disabled href="sub_flow_runs" class="subheader">
        <i class="pi pi-flow-run mr-1 text--grey-40" />
        Sub Flow Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flow_runs' }"
        >
          <!-- {{ subFlowRunsCount.toLocaleString() }} -->
        </span>
      </Tab>
    </Tabs>

    <div class="font--secondary caption my-2" style="min-height: 17px">
      <span v-show="resultsCount.value > 0">
        {{ resultsCount.value?.toLocaleString() }} Result{{
          resultsCount.value !== 1 ? 's' : ''
        }}
      </span>
    </div>

    <section
      class="results-section d-flex flex-column align-stretch justify-stretch"
    >
      <transition name="tab-fade" mode="out-in" css>
        <div
          v-if="resultsCount === 0"
          class="text-center my-8"
          key="no-results"
        >
          <h2> No Results Found </h2>
        </div>

        <results-list
          v-else-if="resultsTab == 'task_runs'"
          key="flows"
          :filter="taskRunsFilter"
          component="task-run-list-item"
          endpoint="task_runs"
        />

        <results-list
          v-else-if="false && resultsTab == 'sub_flow_runs'"
          key="deployments"
          :filter="subFlowRunsFilter"
          component="flow-run-list-item"
          endpoint="flow_runs"
        />
      </transition>
    </section>

    <hr class="results-hr mt-3" />
  </div>
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints, BaseFilter } from '@/plugins/api'
import { State, FlowRun, Deployment } from '@/typings/objects'
import { computed, onBeforeUnmount, onBeforeMount, ref, Ref } from 'vue'
import { useRoute } from 'vue-router'
import { secondsToApproximateString } from '@/util/util'

const route = useRoute()

const resultsTab: Ref<string | null> = ref(null)

const flowRunBase: Query = await Api.query({
  endpoint: Endpoints.flow_run,
  body: {
    id: route.params.id as string
  },
  options: {
    pollInterval: 5000
  }
}).fetch()

const flowId = flowRunBase.response.value.flow_id
const deploymentId = flowRunBase.response.value.deployment_id

const flowFilter = {
  id: flowId
}

const deploymentFilter = {
  id: deploymentId
}

const taskRunsFilter = computed<BaseFilter>(() => {
  return {
    flow_runs: {
      id: {
        any_: [route.params.id as string]
      }
    }
  }
})

const subFlowRunsFilter = computed<BaseFilter>(() => {
  return {
    flow_runs: {
      // parent_task_run_id: {
      //   any_: []
      // }
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
    body: deploymentFilter
  }),
  task_runs: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: taskRunsFilter,
    options: {
      pollInterval: 10000
    }
  })
  // TODO: Need to add a query for task runs with this flow run id that have sub flow runs and pipe that in to this as parent task run id
  // sub_flow_runs: Api.query({
  //   endpoint: Endpoints.flow_runs_count,
  //   body: subFlowRunsFilter,
  //   options: {
  //     pollInterval: 10000
  //   }
  // })
}

const resultsCount = computed(() => {
  if (!resultsTab.value) return 0
  return queries[resultsTab.value]?.response || 0
})

const flow = computed(() => {
  return queries.flow.response?.value || {}
})

const deployment = computed<Deployment>(() => {
  return queries.deployment.response?.value || {}
})

const location = computed(() => {
  return deployment.value?.flow_data?.blob
})

const flowRun = computed<FlowRun>(() => {
  return flowRunBase.response?.value || {}
})

const state = computed<State>(() => {
  return flowRun.value?.state
})

const tags = computed(() => {
  return flowRun.value?.tags || []
})

const crumbs = computed(() => {
  return [{ text: flow.value?.name }, { text: flowRun.value?.name }]
})

const taskRunsCount = computed(() => {
  return queries.task_runs.response?.value || 0
})

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

onBeforeMount(() => {
  resultsTab.value = route.hash?.substr(1) || 'task_runs'
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run.scss';
</style>
