<template>
  <ListItem class="list-item-flow" icon="pi-flow">
    <div class="list-item__title">
      <BreadCrumbs :crumbs="crumbs" tag="h2" />
    </div>

    <div v-if="media.sm" class="ml-auto nowrap">
      <ButtonRounded class="mr-1" @click="filter">
        {{ flowRunCount.toLocaleString() }} flow
        {{ toPluralString('run', flowRunCount) }}
      </ButtonRounded>

      <ButtonRounded class="mr-1" @click="filter">
        {{ taskRunCount.toLocaleString() }} task
        {{ toPluralString('run', taskRunCount) }}
      </ButtonRounded>
    </div>
    <div v-if="media.md" class="list-item-flow__chart-container">
      <RunHistoryChart
        :items="flowRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="0"
        static-median
        :padding="{ top: 3, bottom: 3, left: 3, right: 3, middle: 2 }"
        disable-popovers
      />
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
  import {
    BreadCrumbs,
    Crumb,
    useFiltersStore,
    FlowsFilter,
    FilterUrlService,
    FiltersQueryService,
    media,
    toPluralString,
    showPanel,
    FlowPanel,
    Flow,
    Deployment,
    DeploymentPanel,
    DeploymentsApi,
    FlowRunsApi
  } from '@prefecthq/orion-design'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import ButtonRounded from '@/components/Global/ButtonRounded/ButtonRounded.vue'
  import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
  import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
  import { Api, Query, Endpoints } from '@/plugins/api'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { Buckets } from '@/typings/run_history'
  import { can } from '@/utilities/permissions'

  const props = defineProps<{ item: Flow }>()

  const filtersStore = useFiltersStore()
  const router = useRouter()

  const crumbs: Crumb[] = [{ text: props.item.name, action: openFlowPanel }]

  const runFilter = computed(()=> FiltersQueryService.query(filtersStore.all))
  const flows: FlowsFilter = {
    ...runFilter.value,
    flows: {
      id: {
        any_: [props.item.id],
      },
    },
  }

  const flowRunHistoryFilter = computed(() => {
    const query = FiltersQueryService.flowHistoryQuery(filtersStore.all)

    return {
      ...query,
      history_interval_seconds: query.history_interval_seconds * 2,
      flows: flows.flows,
    }
  })

  const start = computed<Date>(() => new Date(flowRunHistoryFilter.value.history_start))
  const end = computed<Date>(() => new Date(flowRunHistoryFilter.value.history_end))
  const queries: Record<string, Query> = {
    flow_run_history: Api.query({
      endpoint: Endpoints.flow_runs_history,
      body: flowRunHistoryFilter.value,
    }),
    flow_run_count: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: flows,
    }),
    task_run_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: flows,
    }),
  }

  const flowRunCount = computed((): number => {
    return queries.flow_run_count?.response?.value || 0
  })

  const taskRunCount = computed((): number => {
    return queries.task_run_count?.response?.value || 0
  })

  const flowRunHistory = computed((): Buckets => {
    return queries.flow_run_history?.response.value || []
  })

  function filter(): void {
    const service = new FilterUrlService(router)

    service.add({
      object: 'flow',
      property: 'name',
      type: 'string',
      operation: 'equals',
      value: props.item.name,
    })
  }

  const route = { name: 'Dashboard' }

  function openFlowPanel(): void {
    showPanel(FlowPanel, {
      flow: props.item,
      dashboardRoute: route,
      openDeploymentPanel,
      deploymentsApi: deploymentsApi as DeploymentsApi,
      flowRunsApi: flowRunsApi as FlowRunsApi,
      can,
    })
  }

  function openDeploymentPanel(deployment: Deployment): void {
    showPanel(DeploymentPanel, {
      deployment,
      dashboardRoute: route,
      deploymentsApi: deploymentsApi as DeploymentsApi,
      flowRunsApi: flowRunsApi as FlowRunsApi,
    })
  }
</script>

<style lang="scss" scoped>
.list-item-flow__chart-container {
  height: 52px;
  max-width: 175px;
}
</style>
