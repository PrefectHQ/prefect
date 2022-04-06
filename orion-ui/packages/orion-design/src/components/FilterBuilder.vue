<template>
  <div class="filter-builder">
    <div class="filter-builder__header">
      <FilterBuilderHeading class="filter-builder__heading" :filter="innerFilter" />
      <template v-if="dismissible && hasObject">
        <button type="button" class="filter-builder__close" @click="emit('dismiss')">
          <i class="filter-builder__close-icon pi pi-sm pi-close-circle-fill" />
        </button>
      </template>
      <button type="button" class="filter-builder__toggle" :class="classes.toggle" @click="toggle">
        <i class="pi pi-arrow-down-s-line" />
      </button>
    </div>
    <template v-if="innerExpanded">
      <div class="filter-builder__filter">
        <template v-if="!innerFilter.object">
          <FilterBuilderObject v-model:object="innerFilter.object" />
        </template>
        <template v-else-if="!innerFilter.property">
          <FilterBuilderProperty v-model:property="innerFilter.property" v-model:type="innerFilter.type" :object="innerFilter.object" />
        </template>
        <template v-else>
          <FilterBuilderValue v-model:operation="innerFilter.operation" v-model:value="innerFilter.value" :object="innerFilter.object" :property="innerFilter.property" />
        </template>
        <template v-if="isCompleteFilter(innerFilter)">
          <FilterTag class="filter-builder__tag" :filter="innerFilter" />
        </template>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue'
  import FilterBuilderHeading from '@/components/FilterBuilderHeading.vue'
  import FilterBuilderObject from '@/components/FilterBuilderObject.vue'
  import FilterBuilderProperty from '@/components/FilterBuilderProperty.vue'
  import FilterBuilderValue from '@/components/FilterBuilderValue.vue'
  import FilterTag from '@/components/FilterTag.vue'
  import { Filter } from '@/types/filters'
  import { isCompleteFilter } from '@/utilities/filters'

  const emit = defineEmits<{
    (event: 'update:filter', value: Partial<Filter>): void,
    (event: 'dismiss'): void,
    (event: 'update:expanded', value: boolean): void,
  }>()

  const props = defineProps<{
    filter: Partial<Filter>,
    dismissible?: boolean,
    expanded?: boolean,
  }>()

  const innerFilter = computed({
    get: () => props.filter,
    set: (filter) => emit('update:filter', filter),
  })

  const innerExpanded = ref(true)

  watch(() => props.expanded, () => {
    innerExpanded.value = props.expanded ?? true
  }, { immediate: true })

  const hasObject = computed<boolean>(() => !!innerFilter.value.object)

  const classes = computed(() => ({
    toggle: {
      'filter-builder__toggle--closed': innerExpanded.value,
    },
  }))

  function toggle(): void {
    innerExpanded.value = !innerExpanded.value

    emit('update:expanded', innerExpanded.value)
  }
</script>

<style lang="scss">
.filter-builder {
  background-color: #fff;
  padding: var(--p-1) var(--p-2);
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.filter-builder__header {
  margin-bottom: var(--m-1);
  display: flex;
  align-items: center;
}

.filter-builder__heading {
  margin-right: auto;
}

.filter-builder__close,
.filter-builder__toggle {
  appearance: none;
  border: 0;
  background: none;
  cursor: pointer;
  display: flex;
  align-items: center;

}
.filter-builder__close {
  --icon-color: var(--primary);

  &:hover {
    --icon-color: var(--primary-hover);
  }
}

.filter-builder__close-icon {
  color: var(--icon-color);
}

.filter-builder__toggle {
  transform: rotate(180deg);
  transition: transform 0.25s ease;
}

.filter-builder__toggle--closed {
  transform: rotate(0deg);
}

.filter-builder__filter {
  padding-bottom: var(--p-1);
}

.filter-builder__tag {
  margin-top: var(--m-1);
}
</style>