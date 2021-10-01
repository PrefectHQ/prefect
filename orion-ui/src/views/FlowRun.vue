<template>
  <div>
    <bread-crumbs :crumbs="crumbs" icon="pi-flow-run" />
    {{ flowRun }}
    <!-- <Tabs v-model="resultsTab" class="mt-5">
      <Tab href="task_runs" class="subheader">
        <i class="pi pi-task pi-lg mr-1" />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task_runs' }"
        >
          {{ taskRunsCount.toLocaleString() }}
        </span>
      </Tab>

      <Tab href="sub_flow_runs" class="subheader">
        <i class="pi pi-flow-run pi-lg mr-1" />
        Flow Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flow_runs' }"
        >
          {{ subFlowRunsCount.toLocaleString() }}
        </span>
      </Tab>
    </Tabs>

    <div class="font--secondary caption my-2" style="min-height: 17px">
      <span v-show="resultsCount > 0">
        {{ resultsCount.toLocaleString() }} Result{{
          resultsCount !== 1 ? 's' : ''
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
          :filter="taskRunFilter"
          component="task-run-list-item"
          endpoint="task_runs"
        />

        <results-list
          v-else-if="resultsTab == 'sub_flow_runs'"
          key="deployments"
          :filter="subFlowRunFilter"
          component="flow-run-list-item"
          endpoint="flow_runs"
        />
      </transition>
    </section>
    <hr class="results-hr mt-3" /> -->
  </div>
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints, FlowRunsFilter } from '@/plugins/api'
import { computed, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

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

const flowFilter = {
  id: flowId
}

const queries: { [key: string]: Query } = {
  flow: Api.query({
    endpoint: Endpoints.flow,
    body: flowFilter
  })
  // task_runs_count: Api.query({
  //   endpoint: Endpoints.flow_run,
  //   body: {
  //     id: id.value
  //   },
  //   options: {
  //     pollInterval: 5000
  //   }
  // }),
  // sub_flow_runs_count: Api.query({
  //   endpoint: Endpoints.flow_run,
  //   body: {
  //     id: id.value
  //   },
  //   options: {
  //     pollInterval: 5000
  //   }
  // })
}

const flow = computed(() => {
  return queries.flow.response?.value
})

const flowRun = computed(() => {
  return flowRunBase.response?.value
})

const crumbs = computed(() => {
  return [{ text: flow.value?.name }, { text: flowRun.value?.name }]
})

// This cleanup is necessary since the initial flow run query isn't
// wrapped in the queries object
onBeforeUnmount(() => {
  flowRunBase.stopPolling()
  Api.queries.delete(flowRunBase.id)
})

// const id = computed(() => {
//   return route.params.id
// })

// const baseFilter = computed(() => {
//   return {
//     flows: {}
//   }
// })

// const flowFilter = computed(() => {
//   return {
//     id: flow.value.id
//   }
// })

// const flow = computed(() => {
//   return queries.flow.response?.value.flow_id
// })

// const flowRun = computed(() => {
//   return queries.flow_run.response?.value
// })
</script>
