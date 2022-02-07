<template>
  <div class="filter-builder-object">
    <template v-for="object in objects" :key="object">
      <m-button color="secondary" :icon="FilterService.icon({ object })" miter @click="emit('update:object', object)">
        {{ FilterDescriptionService.object(object) }}
      </m-button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { FilterDescriptionService } from '../services/FilterDescriptionService'
  import { FilterService } from '../services/FilterService'
  import { FilterObject } from '../types/filters'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'update:object', value: FilterObject): void,
  }>()

  const objects: FilterObject[] = ['flow', 'deployment', 'flow_run', 'task_run', 'tag']
</script>

<style lang="scss" scoped>
.filter-builder-object {
  display: flex;
  gap: var(--m-1);
  flex-wrap: wrap;
}
</style>