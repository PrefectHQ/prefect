<template>
  <div class="filter-builder-object">
    <template v-for="object in objects" :key="object">
      <m-button color="secondary" :icon="FilterService.icon({ object })" miter @click="filter.object = object">
        <span class="filter-builder-object__name">{{ FilterDescriptionService.object(object) }}</span>
      </m-button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { FilterDescriptionService } from '@/services/FilterDescriptionService'
  import { FilterService } from '@/services/FilterService'
  import { Filter, FilterObject } from '@/types/filters'
import { computed } from 'vue';

  const emit = defineEmits<{
    (event: 'update:filter', value: Partial<Filter>): void,
  }>()

  const props = defineProps<{
    filter: Partial<Filter>,
  }>()

  const objects: FilterObject[] = ['flow', 'deployment', 'flow_run', 'task_run']

  const filter = computed({
    get() {
      return props.filter
    },
    set(filter: Partial<Filter>) {
      emit('update:filter', filter)
    }
  })
</script>

<style lang="scss">
.filter-builder-object {
  display: flex;
  gap: var(--m-1);
  flex-wrap: wrap;
}

.filter-builder-object__name::first-letter {
  text-transform: uppercase;
}
</style>