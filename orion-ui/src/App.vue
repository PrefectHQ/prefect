<template>
  <div class="application">
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
  import { FilterBar } from '@prefecthq/orion-design'
  import { computed } from 'vue'
  import { useRoute } from 'vue-router'
  import NavBar from '@/components/NavBar.vue'

  const route = useRoute()

  const filtersVisible = computed(() => route.meta.filters?.visible ?? false)
  const filtersDisabled = computed(() => route.meta.filters?.disabled ?? false)
</script>

<style lang="scss">
.application {
  background-color: var(--grey-10);
  display: grid;
  grid-template-areas:
    'nav filter-bar'
    'nav main';
  grid-template-columns: 62px 1fr;
  grid-template-rows: 62px 1fr;
  row-gap: 16px;
  min-height: 100vh;

  @media (max-width: 640px) {
    grid-template-areas:
      'nav'
      'filter-bar'
      'main';
    grid-template-columns: unset;
    grid-template-rows: 62px 62px 1fr;
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
}

.application__nav {
  grid-area: nav;
}
</style>
