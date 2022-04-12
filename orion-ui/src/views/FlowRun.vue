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
      <BreadCrumbs class="flex-grow-1" :crumbs="crumbs" icon="flow-run" />
      <template v-if="route.fullPath.includes('/radar')">
        <div v-if="media.sm" class="text-truncate d-flex align-center">
          <span class="ml-5">
            Flow Version:
            <span class="font-weight-semibold">
              {{ version }}
            </span>
          </span>
          <CopyButton
            v-if="media.md"
            class="ml-1"
            :value="id"
            toast="Run ID was copied to clipboard"
          >
            Copy Run ID
          </CopyButton>
        </div>
      </template>
    </div>

    <router-view />
  </div>
</template>

<script lang="ts" setup>
  import { CopyButton, useFiltersStore, media, BreadCrumbs } from '@prefecthq/orion-design'
  import { computed, onBeforeUnmount, onBeforeMount, ref, Ref, watch } from 'vue'

  import { useRoute, onBeforeRouteLeave } from 'vue-router'
  import { Api, Query, Endpoints } from '@/plugins/api'
  import { FlowRun, Flow } from '@/typings/objects'

  const filtersStore = useFiltersStore()

  const route = useRoute()

  const resultsTab: Ref<string | null> = ref(null)

  const id = ref(route?.params.id as string)

  const idWatcher = watch(route, () => {
    id.value = route?.params.id as string
  })

  onBeforeRouteLeave(() => {
    idWatcher()
  })

  const version = computed<string>(() => {
    return flowRun.value.flow_version ?? '--'
  })

  const flowRunBaseBody = computed(() => {
    return {
      id: id.value,
    }
  })

  const flowRunBase: Query = await Api.query({
    endpoint: Endpoints.flow_run,
    body: flowRunBaseBody,
    options: {
      pollInterval: 5000,
    },
  }).fetch()

  const flowBody = computed(() => {
    return {
      id: flowRunBase.response.value.flow_id,
    }
  })

  const queries: Record<string, Query> = {
    flow: Api.query({
      endpoint: Endpoints.flow,
      body: flowBody,
    }),
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
      { text: flowRun.value?.name, to: '' },
    ]

    const timelinePage = route.fullPath.includes('/timeline')
    const radarPage = route.fullPath.includes('/radar')
    if (timelinePage || radarPage) {
      arr[1].to = `/flow-run/${id.value}`

      if (timelinePage) {
        arr.push({ text: 'Timeline' })
      }
      if (radarPage) {
        arr.push({ text: 'Radar' })
      }
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

  watch(id, () => {
    if (!id.value) {
      return
    }
    queries.flow.fetch()
  })

  const flowRunWatcher = watch(() => flowRun.value, () => {
    if (flowRun.value.name && filtersStore.all.length == 0) {
      filtersStore.replaceAll([
        {
          object: 'flow_run',
          property: 'name',
          type: 'string',
          operation: 'equals',
          value: flowRun.value.name,
        },
      ])

      flowRunWatcher()
    }
  })
</script>

<style lang="scss" scoped>
.blur {
  backdrop-filter: blur(1px);
  background-color: rgba(244, 245, 247, 0.8);
  border-radius: 8px;
}
</style>
