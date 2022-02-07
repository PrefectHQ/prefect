<template>
  <div class="filter-builder-object">
    <template v-for="obj in objects" :key="obj">
      <m-button color="secondary" :icon="FilterService.icon({ object: obj })" miter @click="emit('update:object', obj)">
        <span class="filter-builder-object__name">{{ FilterDescriptionService.object(obj) }}</span>
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

  defineProps<{
    // object is used for the v-model but not accessed
    // eslint-disable-next-line vue/no-unused-properties
    object?: FilterObject,
  }>()

  const objects: FilterObject[] = ['flow', 'deployment', 'flow_run', 'task_run', 'tag']
</script>

<style lang="scss" scoped>
.filter-builder-object {
  display: flex;
  gap: var(--m-1);
  flex-wrap: wrap;
}

.filter-builder-object__name::first-letter {
  text-transform: uppercase;
}
</style>