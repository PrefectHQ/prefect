<template>
  <div class="application">
    <NavBar class="nav" />
    <FilterBar v-if="validFilterRoute" class="filter-bar" />
    <suspense>
      <router-view class="router-view" />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
import NavBar from '@/components/ApplicationNav/NavBar.vue'
import FilterBar from '@/components/FilterBar/FilterBar.vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const validRoutes = ['/', '/flow-run']

const validFilterRoute = computed(() => {
  return validRoutes.includes(route.path)
})
</script>

<style lang="scss">
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.application {
  background-color: $grey-10;
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

  .nav {
    grid-area: nav;
  }

  .filter-bar {
    grid-area: filter-bar;
  }

  .router-view {
    grid-area: main;
    padding: 0 32px;
    overflow: auto;

    @media (max-width: 640px) {
      padding: 0px 16px 32px 16px;
    }
  }
}
</style>
