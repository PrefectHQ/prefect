<template>
  <div class="application" :class="classes.root" data-teleport-target="app">
    <NavBar class="application__nav" />
    <template v-if="filtersVisible">
      <FilterBar class="application__filter-bar" :disabled="filtersDisabled" />
    </template>
    <suspense>
      <router-view class="application__router-view" />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import { deploymentsApiKey, FilterBar, filtersDefaultObjectKey, flowRunsApiKey, flowsApiKey, logsApiKey, searchApiKey, taskRunsApiKey, workQueuesApiKey, canKey } from '@prefecthq/orion-design'
  import { computed, provide } from 'vue'
  import { useRoute } from 'vue-router'
  import NavBar from '@/components/NavBar.vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'
  import { logsApi } from '@/services/logsApi'
  import { can } from '@/services/permissions'
  import { searchApi } from '@/services/searchApi'
  import { taskRunsApi } from '@/services/taskRunsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const route = useRoute()

  provide(deploymentsApiKey, deploymentsApi)
  provide(flowRunsApiKey, flowRunsApi)
  provide(flowsApiKey, flowsApi)
  provide(logsApiKey, logsApi)
  provide(searchApiKey, searchApi)
  provide(taskRunsApiKey, taskRunsApi)
  provide(workQueuesApiKey, workQueuesApi)
  provide(filtersDefaultObjectKey, 'flow_run')
  provide(canKey, can)

  const filtersVisible = computed(() => route.meta.filters?.visible ?? false)
  const filtersDisabled = computed(() => route.meta.filters?.disabled ?? false)
  const classes = computed(() => {
    return {
      root: {
        'application--with-filters': filtersVisible.value,
      },
    }
  })
</script>

<style lang="scss">
.application {
  background-color: var(--grey-10);
  display: grid;
  grid-template-areas: 'nav main';
  grid-template-columns: 62px minmax(0, 1fr);
  min-height: 100vh;

  @media (max-width: 640px) {
    grid-template-areas:
      'nav'
      'main';
    grid-template-columns: unset;
    grid-template-rows: 62px minmax(0, 1fr);
    row-gap: 0;
  }
}

.application--with-filters {
  grid-template-areas:
    'nav filter-bar'
    'nav main';
  grid-template-rows: 62px minmax(0, 1fr);
  row-gap: 16px;

  @media (max-width: 640px) {
    grid-template-areas:
      'nav'
      'filter-bar'
      'main';
    grid-template-columns: unset;
    grid-template-rows: 62px 62px minmax(0, 1fr);
    row-gap: 0;
  }
}

.application__router-view {
  grid-area: main;
  padding: 0 32px;
  overflow: auto;

  @media (max-width: 640px) {
    padding: 0px 16px 32px 16px;
  }
}

.application__filter-bar {
  grid-area: filter-bar;
  min-width: 0;
}

.application__nav {
  grid-area: nav;
}
</style>
