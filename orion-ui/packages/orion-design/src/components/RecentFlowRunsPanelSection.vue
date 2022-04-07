<template>
  <PanelSection icon="flow-run">
    <template #heading>
      <div class="recent-flow-runs-panel-section__heading">
        Recent &amp; Upcoming Runs <span class="recent-flow-runs-panel-section__subheading">past week, next week</span>
        <button type="button" class="recent-flow-runs-panel-section__all" @click="viewAll">
          View all
        </button>
      </div>
    </template>

    <div class="recent-flow-runs-panel-section__counts">
      <template v-for="(subscription, type) in subscriptions" :key="type">
        <FilterButtonCard :route="dashboardRoute" :count="subscription?.response" :label="type" :filters="typeFilter(type)" />
      </template>
    </div>
  </PanelSection>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { RouteLocationRaw, useRouter } from 'vue-router'
  import FilterButtonCard from '@/components/FilterButtonCard.vue'
  import PanelSection from '@/components/PanelSection.vue'
  import { StateType } from '@/models/StateType'
  import { UnionFilters } from '@/services/Filter'
  import { FilterService } from '@/services/FilterService'
  import { FiltersQueryService } from '@/services/FiltersQueryService'
  import { FlowRunsApi } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'

  const props = defineProps<{
    baseFilter: Required<Filter>,
    dashboardRoute: Exclude<RouteLocationRaw, string>,
    flowRunsApi: FlowRunsApi,
  }>()

  const router = useRouter()

  const viewAllFilter = computed<Required<Filter>[]>(() => [
    props.baseFilter,
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'last',
      value: '1w',
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'next',
      value: '1w',
    },
  ])

  function typeUnionFilter(type: StateType): UnionFilters {
    const query = FiltersQueryService.query(viewAllFilter.value)

    if (!query.flow_runs) {
      query.flow_runs = {}
    }

    query.flow_runs.state = {
      type: {
        any_: [type],
      },
    }

    return query
  }

  function typeFilter(type: StateType): Required<Filter>[] {
    return [
      ...viewAllFilter.value,
      {
        object: 'flow_run',
        property: 'state',
        type: 'state',
        operation: 'or',
        value: [type],
      },
    ]
  }

  function viewAll(): void {
    const filter = FilterService.stringify(viewAllFilter.value)

    router.push({ ...props.dashboardRoute, query: { filter } })
  }

  const options = {
    interval: 30000,
  }

  const subscriptions = {
    COMPLETED: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('COMPLETED')], options),
    RUNNING: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('RUNNING')], options),
    SCHEDULED: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('SCHEDULED')], options),
    PENDING: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('PENDING')], options),
    FAILED: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('FAILED')], options),
    CANCELLED: useSubscription(props.flowRunsApi.getFlowRunsCount, [typeUnionFilter('CANCELLED')], options),
  }
</script>

<style lang="scss">
@use 'sass:map';
.recent-flow-runs-panel-section__heading {
  display: flex;
  width: 100%;
  align-items: baseline;
  gap: 3px;
  flex-wrap: wrap;
}

.recent-flow-runs-panel-section__subheading,
.recent-flow-runs-panel-section__all {
  font-weight: 400;
  line-height: 24px;
  color: var(--grey-80);
}

.recent-flow-runs-panel-section__subheading {
  font-size: 14px;
}

.recent-flow-runs-panel-section__all {
  font-size: 16px;
  appearance: none;
  border: 0;
  cursor: pointer;
  background: none;
  margin-left: auto;
}

.recent-flow-runs-panel-section__counts {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;

  @media only screen and (min-width: map.get($breakpoints, 'xs')) {
    grid-template-columns: 1fr 1fr;
  }
}
</style>