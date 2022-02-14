<template>
  <div class="filter-tags">
    <template v-for="filter in filters" :key="filter.id">
      <FilterTag class="filter-tags__tag" v-bind="{ filter, dismissible }" @dismiss="emit('dismiss', filter)" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { FilterState } from '../stores/filters'
  import FilterTag from './FilterTag.vue'

  const emit = defineEmits<{
    (event: 'dismiss', filter: FilterState): void,
  }>()

  type Props = {
    filters: FilterState[],
    dismissible?: boolean,
  }

  defineProps<Props>()
</script>

<style lang="scss" scoped>
.filter-tags {
  display: flex;
  gap: var(--m-1)
}

.filter-tags__tag {
  opacity: 1;
}
</style>