<template>
  <button type="button" class="filter-tag" :class="classes" @click="dismiss(filter)">
    <span class="filter-tag__label">{{ label }}</span>
    <template v-if="dismissible">
      <i class="filter-tag__icon pi pi-xs pi-close-circle-fill" />
    </template>
  </button>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { FilterService } from '../services/FilterService'
  import { Filter } from '../types/filters'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'dismiss', filter: Required<Filter>): void,
  }>()

  type Props = {
    filter: Required<Filter>,
    dismissible?: boolean,
  }

  const props = defineProps<Props>()

  const label = computed<string>(() => FilterService.stringify(props.filter))
  const classes = computed(() => ({
    'filter-tag--dismissible': props.dismissible,
  }))

  function dismiss(filter: Required<Filter>): void {
    if (props.dismissible) {
      emit('dismiss', filter)
    }
  }
</script>

<style lang="scss" scoped>
.filter-tag {
  --background: var(--blue-20);
  --color: var(--grey-80);
  --icon-color: var(--primary);

  appearance: none;
  border: 0;
  background-color: var(--background);
  color: var(--color);
  border-radius: 4px;
  font-size: 14px;
  font-family: var(--font-secondary);
  padding: calc(var(--p-1) * 0.5) var(--p-1);
  display: flex;
  align-items: center;
  gap: var(--p-1);
  clip-path: var(--miter-clip-path);
}

.filter-tag--dismissible {
  cursor: pointer;

  &:hover {
    --background: var(--primary);
    --color: #fff;
    --icon-color: #fff;
  }

  &:active {
    --background: var(--primary-hover);
  }
}

.filter-tag--invalid {
  --background: #fb4e4e;
}

.filter-tag__icon {
  color: var(--icon-color);
  transition: inherit;
  display: block;
}
</style>