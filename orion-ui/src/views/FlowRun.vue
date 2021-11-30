<template>
  <div>
    <div
      class="
        d-flex
        align-center
        justify-space-between
        mb-2
        py-1
        position-relative
        z-1
      "
      :class="{ blur: route.fullPath.includes('/radar') }"
    >
      <bread-crumbs class="flex-grow-1" :crumbs="crumbs" icon="pi-flow-run" />
      <div v-breakpoints="'sm'" class="text-truncate">
        <span>
          Flow Version:
          <span class="font-weight-semibold">{{ flowRun.flow_version }}</span>
        </span>

        <button v-breakpoints="'md'" class="copy-link ml-1" @click="copyRunId">
          <i class="pi pi-link pi-xs" />
          Copy Run ID
        </button>
      </div>
    </div>

    <router-view />
  </div>
</template>

<script lang="ts" setup>
import { Api, Query, Endpoints } from '@/plugins/api'
import { FlowRun, Flow } from '@/typings/objects'
import { computed, onBeforeUnmount, onBeforeMount, ref, Ref, watch, getCurrentInstance } from 'vue'

import { useRoute } from 'vue-router'

const route = useRoute()

const resultsTab: Ref<string | null> = ref(null)

const id = computed<string>(() => {
  return route?.params.id as string
})

const flowRunBaseBody = computed(() => {
  return {
    id: id.value
  }
})

const flowRunBase: Query = await Api.query({
  endpoint: Endpoints.flow_run,
  body: flowRunBaseBody,
  options: {
    pollInterval: 5000
  }
}).fetch()

const flowBody = computed(() => {
  return {
    id: flowRunBase.response.value.flow_id
  }
})

const queries: { [key: string]: Query } = {
  flow: Api.query({
    endpoint: Endpoints.flow,
    body: flowBody
  })
}

const flow = computed<Flow>(() => {
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
  const radarPage = route.fullPath.includes('/radar')
  if (timelinePage || radarPage) {
    arr[1].to = `/flow-run/${id.value}`

    if (timelinePage) arr.push({ text: 'Timeline' })
    if (radarPage) arr.push({ text: 'Radar' })
  }

  return arr
})

const instance = getCurrentInstance()

const copyRunId = () => {
  navigator.clipboard.writeText(id.value)
  instance?.appContext.config.globalProperties.$toast.add({
    type: 'success',
    content: 'Run ID was copied to clipboard'
  })
}

// This cleanup is necessary since the initial flow run query isn't
// wrapped in the queries object
onBeforeUnmount(() => {
  flowRunBase.stopPolling()
  Api.queries.delete(flowRunBase.id)
})

onBeforeMount(() => {
  resultsTab.value = route.hash?.substr(1) || 'task_runs'
})

watch(id, () => {
  queries.flow.fetch()
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run.scss';
</style>
