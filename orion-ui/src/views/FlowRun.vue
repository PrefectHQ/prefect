<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-2">
      <bread-crumbs :crumbs="crumbs" icon="pi-flow-run" />
      <div>
        <span>
          Flow Version:
          <span class="font-weight-semibold">{{ flowRun.flow_version }}</span>
        </span>

        <a class="copy-link ml-1">
          <i class="pi pi-link pi-xs" />
          Copy Run ID
        </a>
      </div>
    </div>

    <div class="main-grid">
      <Card class="details" shadow="sm">details</Card>
      <Card class="timeline" shadow="sm">timeline</Card>
      <Card class="schematic" shadow="sm">schematic</Card>
    </div>

    <Tabs v-model="resultsTab" class="mt-3">
      <Tab href="task_runs" class="subheader">
        <i class="pi pi-task mr-1 text--grey-40" />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task_runs' }"
        >
          <!-- {{ taskRunsCount.toLocaleString() }} -->
        </span>
      </Tab>

      <Tab href="sub_flow_runs" class="subheader">
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

    <!-- 

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
import { Api, Query, Endpoints } from '@/plugins/api'
import { computed, onBeforeUnmount, onBeforeMount, ref, Ref } from 'vue'
import { useRoute } from 'vue-router'

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
  return queries.flow.response?.value || {}
})

const flowRun = computed(() => {
  return flowRunBase.response?.value || {}
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

onBeforeMount(() => {
  resultsTab.value = route.hash?.substr(1) || 'flows'
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

<style lang="scss" scoped>
@use '@/styles/views/flow-run.scss';
</style>
