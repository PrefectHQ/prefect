<template>
  <div class="filter-builder-heading">
    <i class="filter-builder-heading__icon" :class="icon" />
    <span class="filter-builder-heading__label">{{ label }}</span>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { FilterService } from '../services/FilterService'
  import { Filter } from '../types/filters'
  import { isFilter } from '../utilities/filters'

  type Props = {
    filter: Partial<Filter>,
  }

  const props = defineProps<Props>()

  const label = computed(() => {
    if (isFilter(props.filter)) {
      return FilterService.describe(props.filter)
    }

    return 'Add filter for...'
  })

  const icon = computed(() => {
    if (isFilter(props.filter)) {
      return FilterService.icon(props.filter)
    }

    return 'pi-filter-3-line'
  })
</script>

<style lang="scss" scoped>
.filter-builder-heading {
  color: var(--black);
  font-family: var(--primary);
  font-size: 16px;
  font-weight: 600;
  line-height: 28px;
  display: flex;
  align-items: center;
  gap: var(--p-1);
}

.filter-builder-heading__icon {
  font-size: 1.5em;
}
</style>