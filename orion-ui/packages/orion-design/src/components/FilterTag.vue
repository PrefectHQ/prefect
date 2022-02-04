<template>
  <span class="filter-tag">
    {{ label }}
  </span>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Filter } from '../types/filters'

  type Props = {
    filter: Required<Filter>,
  }

  const props = defineProps<Props>()

  const label = computed<string>(() => props.filter.value)
</script>

<style lang="scss" scoped></style>