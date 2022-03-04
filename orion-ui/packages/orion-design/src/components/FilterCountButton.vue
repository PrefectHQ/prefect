<template>
  <button type="button" class="filter-button" :class="classes" @click="applyFilters">
    {{ countLabel }}
  </button>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { RouteLocationRaw, useRoute, useRouter } from 'vue-router'
  import { FilterService } from '@/services/FilterService'
  import { Filter } from '@/types/filters'
  import { toPluralString } from '@/utilities/strings'

  const props = defineProps<{
    filters: Required<Filter>[],
    count: number,
    label: string,
    route?: Exclude<RouteLocationRaw, string>,
    disabled?: boolean,
  }>()

  const router = useRouter()
  const currentRoute = useRoute()

  const countLabel = computed(() => `${props.count.toLocaleString()} ${toPluralString(props.label, props.count)}`)

  const classes = computed(() => ({
    'filter-button--disabled': props.disabled,
  }))

  function applyFilters(): void {
    const filter = FilterService.stringify(props.filters)

    if (props.route) {
      router.push({ ...props.route, query: { ...props.route.query, filter } })
    } else {
      router.push({ query: { ...currentRoute.query, filter } })
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
