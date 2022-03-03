<template>
  <button type="button" class="filter-button" :class="classes" @click="applyFilters">
    <slot />
  </button>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { RouteLocationRaw, useRoute, useRouter } from 'vue-router'
  import { FilterService } from '../services/FilterService'
  import { Filter } from '../types/filters'

  const props = defineProps<{
    filters: Required<Filter>[],
    route?: RouteLocationRaw,
    disabled?: boolean,
  }>()

  const router = useRouter()
  const currentRoute = useRoute()

  const classes = computed(() => ({
    'filter-button--disabled': props.disabled,
  }))

  function applyFilters(): void {
    const filters = FilterService.stringify(props.filters)

    if (props.route && typeof props.route !== 'string') {
      router.push({ ...props.route, query: { ...props.route.query, filter: filters } })
    } else {
      router.push({ query: { ...currentRoute.query, filter: filters } })
    }
  }
</script>

<style lang="scss">
.filter-button {
  background: none;
  border-radius: 100px;
  border: 1px solid var(--blue-20);
  color: var(--primary);
  cursor: pointer;
  font-size: 12px;
  font-family: $font--secondary;
  height: min-content;
  padding: 2px 8px;
  user-select: none;
  white-space: nowrap;
  width: min-content;

  &::-moz-focus-inner {
    outline: none;
  }

  &:not(.filter-button--disabled) {
    &:hover,
    &:focus,
    &:focus-visible,
    &:focus-within {
      outline: none;
      background-color: var(--secondary-hover);
    }
    &:active {
      background-color: var(--secondary-pressed);
    }
  }
}
.filter-button--disabled {
  cursor: text;
  color: var(--grey-80);
}
</style>
