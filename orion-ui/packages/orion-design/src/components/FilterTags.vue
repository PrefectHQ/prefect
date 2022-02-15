<template>
  <div class="filter-tags">
    <template v-for="filter in filters" :key="filter.id">
      <FilterTag class="filter-tags__tag" v-bind="{ filter, dismissible }" @dismiss="emit('dismiss', filter)" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import FilterTag from '@/components/FilterTag.vue'
  import { FilterState } from '@/stores/filters'

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