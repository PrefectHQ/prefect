<template>
  <div class="filter-builder">
    <div class="filter-builder__header">
      <FilterBuilderHeading :filter="innerFilter" />
      <template v-if="dismissable && hasObject">
        <button type="button" class="filter-builder__close" @click="emit('dismiss')">
          <i class="filter-builder__close-icon pi pi-xs pi-close-circle-fill" />
        </button>
      </template>
    </div>
    <template v-if="!innerFilter.object">
      <FilterBuilderObject v-model:object="innerFilter.object" />
    </template>
    <template v-else-if="!innerFilter.property">
      <FilterBuilderProperty v-model:property="innerFilter.property" v-model:type="innerFilter.type" :object="innerFilter.object" />
    </template>
    <template v-else>
      <FilterBuilderValue v-model:type="innerFilter.type" v-model:operation="innerFilter.operation" v-model:value="innerFilter.value" :property="innerFilter.property" />
    </template>
    <template v-if="isCompleteFilter(innerFilter)">
      <FilterTag class="filter-builder__tag" :filter="innerFilter" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Filter } from '../types/filters'
  import { isCompleteFilter } from '../utilities/filters'
  import FilterBuilderHeading from './FilterBuilderHeading.vue'
  import FilterBuilderObject from './FilterBuilderObject.vue'
  import FilterBuilderProperty from './FilterBuilderProperty.vue'
  import FilterBuilderValue from './FilterBuilderValue.vue'
  import FilterTag from './FilterTag.vue'

  // eslint really doesn't like defineEmits type annotation syntax
  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    // eslint-disable-next-line no-unused-vars
    (event: 'update:filter', value: Partial<Filter>): void,
    // eslint-disable-next-line no-unused-vars
    (event: 'dismiss'): void,
  }>()

  const props = defineProps<{
    filter: Partial<Filter>,
    dismissable?: boolean,
  }>()

  const innerFilter = computed({
    get: () => props.filter,
    set: (filter) => emit('update:filter', filter),
  })

  const hasObject = computed<boolean>(() => !!innerFilter.value.object)
</script>

<style lang="scss" scoped>
.filter-builder {
  background-color: #fff;
  padding: var(--p-1) var(--p-2);
}

.filter-builder__header {
  margin-bottom: var(--m-1);
  display: flex;
  align-items: center;
}

.filter-builder__close {
  --icon-color: var(--primary);

  appearance: none;
  border: 0;
  background: none;
  cursor: pointer;
  margin-left: auto;
  display: flex;
  align-items: center;

  &:hover {
    --icon-color: var(--primary-hover);
  }
}

.filter-builder__close-icon {
  color: var(--icon-color);
}

.filter-builder__tag {
  margin-top: var(--m-1);
}
</style>