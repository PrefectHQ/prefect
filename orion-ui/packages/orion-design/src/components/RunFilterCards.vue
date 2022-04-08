<template>
  <div class="run-filter-cards">
    <template v-for="({ label, count, type }) in filters" :key="label">
      <ButtonCard shadow="sm" @click="applyFilter(type)">
        <div class="run-filter-card">
          <div>
            <span class="font--secondary subheader">
              {{ count.toLocaleString() }}
            </span>
            <span class="ml-1 body">{{ label }}</span>
          </div>
          <i class="pi pi-filter-3-line pi-lg text--grey-80" />
        </div>
      </ButtonCard>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import ButtonCard from '@/components/ButtonCard.vue'
  import { useFilterQuery } from '@/compositions/useFilterQuery'
  import { StateType } from '@/models/StateType'
  import { UnionFilters } from '@/services/Filter'
  import { FilterUrlService } from '@/services/FilterUrlService'
  import { flowRunsApiKey } from '@/services/FlowRunsApi'
  import { States } from '@/types/states'
  import { inject } from '@/utilities/inject'


  type PreMadeFilter = {
    label: string,
    count: string | number,
    type: StateType,
    name: string,
  }

  const filter = useFilterQuery()
  const router = useRouter()

  const failedFlowRunsFilter = computed<UnionFilters>(() => ({
    ...filter.value,
    flow_runs: {
      ...filter.value.flow_runs,
      state: {
        type: {
          any_: [States.FAILED],
        },
      },
    },
  }))

  const lateFlowRunsFilter = computed<UnionFilters>(() => ({
    ...filter.value,
    flow_runs: {
      ...filter.value.flow_runs,
      state: {
        name: {
          any_: ['Late'],
        },
      },
    },
  }))

  const scheduledFlowRunsFilter = computed<UnionFilters>(() => ({
    ...filter.value,
    flow_runs: {
      ...filter.value.flow_runs,
      state: {
        name: {
          any_: ['Scheduled'],
        },
      },
    },
  }))

  const flowRunsApi = inject(flowRunsApiKey)
  const failedFlowRunsSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [failedFlowRunsFilter])
  const lateFlowRunsSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [lateFlowRunsFilter])
  const scheduledFlowRunsSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [scheduledFlowRunsFilter])
  const defaultCountValue = '--'

  const filters = computed<PreMadeFilter[]>(() => [
    {
      label: 'Failed Runs',
      count: failedFlowRunsSubscription.response ?? defaultCountValue,
      type: States.FAILED,
      name: 'Failed',
    },
    {
      label: 'Late Runs',
      count: lateFlowRunsSubscription.response ?? defaultCountValue,
      type: States.SCHEDULED,
      name: 'Late',
    },
    {
      label: 'Upcoming Runs',
      count: scheduledFlowRunsSubscription.response ?? defaultCountValue,
      type: States.SCHEDULED,
      name: 'Scheduled',
    },
  ])

  function applyFilter(type: StateType): void {
    const service = new FilterUrlService(router)

    service.add({
      object: 'flow_run',
      property: 'state',
      type: 'state',
      operation: 'or',
      value: [type],
    })
  }
</script>

<style lang="scss">
.run-filter-cards {
  --margin: var(--m-2);

  display: grid;
  grid-template-columns: repeat(3, auto);
  gap: var(--m-2);
  overflow: auto;
  white-space: nowrap;
  margin-left: calc(var(--margin) * -1);
  margin-right: calc(var(--margin) * -1);
  padding: var(--p-1) var(--margin);
  width: calc(100% + var(--margin) * 2);

  scrollbar-width: none; // Edge
  -ms-overflow-style: none; // Firefox

  // Chrome, Safari
  ::-webkit-scrollbar {
    display: none;
  }

  @media (min-width: 640px) {
    --margin: var(--m-4);
  }
}

.run-filter-card {
  padding: 0 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 250px;
  width: 100%;
}
</style>
