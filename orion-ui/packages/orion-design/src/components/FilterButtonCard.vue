<template>
  <button type="button" class="filter-button-card" :class="classes" @click="applyFilters">
    <span class="filter-button-card__count">
      {{ filterCountLabel.toLocaleString() }}
    </span>
    <span class="filter-button-card__label">{{ label }}</span>
    <i class="filter-button-card__icon pi pi-filter-3-line" />
  </button>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { RouteLocationRaw, useRoute, useRouter } from 'vue-router'
  import { FilterService } from '@/services/FilterService'
  import { Filter } from '@/types/filters'

  const props = defineProps<{
    label: string,
    count?: number,
    filters: Required<Filter>[],
    route?: Exclude<RouteLocationRaw, string>,
    disabled?: boolean,
  }>()

  const router = useRouter()
  const currentRoute = useRoute()

  const classes = computed(() => ({
    'filter-button-card--disabled': props.disabled,
  }))

  const filterCountLabel = computed(() => props.count ?? '--')

  function applyFilters(): void {
    if (props.disabled) {
      return
    }

    const filter = FilterService.stringify(props.filters)

    if (props.route) {
      router.push({ ...props.route, query: { ...props.route.query, filter } })
    } else {
      router.push({ query: { ...currentRoute.query, filter } })
    }
  }
</script>

<style lang="scss">
.filter-button-card {
  padding: 0 8px;
  display: flex;
  align-items: center;
  font-size: 16px;
  line-height: 24px;
  color: var(--grey-80);
  gap: var(--m-1);
  border: 1px solid var(--grey-20);
  background-color: #fff;
  outline: none;
  border-radius: 4px;
  cursor: pointer;
  height: 36px;
}

.filter-button-card--disabled {
  cursor: text;
  color: var(--grey-80);
}

.filter-button-card__count {
  font-family: var(--font-secondary);
  position: relative;
  top: 0.1em;
}

.filter-button-card__label {
  font-family: var(--font-primary);
}

.filter-button-card__icon {
  margin-left: auto;
}
</style>