<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-2">
      <BreadCrumbs class="flex-grow-1" :crumbs="crumbs" icon="pi-flow-run" />
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

    <router-view />
  </div>
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints } from '@/plugins/api'
import { FlowRun } from '@/typings/objects'
import { computed, onBeforeUnmount, onBeforeMount, ref, Ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const resultsTab: Ref<string | null> = ref(null)

const id: string = route.params.id as string

const flowRunBase: Query = await Api.query({
  endpoint: Endpoints.flow_run,
  body: {
    id: id
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
}

const flow = computed(() => {
  return queries.flow.response?.value || {}
})

const flowRun = computed<FlowRun>(() => {
  return flowRunBase.response?.value || {}
})

const crumbs = computed(() => {
  const arr = [
    { text: flow.value?.name },
    { text: flowRun.value?.name, to: '' }
  ]

  const timelinePage = route.fullPath.includes('/timeline')
  const schematicPage = route.fullPath.includes('/schematic')
  if (timelinePage || schematicPage) {
    arr[1].to = `/flow-run/${id}`

    if (timelinePage) arr.push({ text: 'Timeline' })
    if (schematicPage) arr.push({ text: 'Schematic' })
  }

  return arr
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
