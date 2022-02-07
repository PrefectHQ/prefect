<template>
  <div class="filter-builder">
    <div class="filter-builder__header">
      <FilterBuilderHeading :filter="filter" />
      <template v-if="hasObject">
        <button type="button" class="filter-builder__close" @click="emit('remove')">
          <i class="filter-builder__close-icon pi pi-xs pi-close-circle-fill" />
        </button>
      </template>
    </div>
    <template v-if="!filter.object">
      <FilterBuilderObject v-model:object="filter.object" />
    </template>
    <template v-else-if="!filter.property">
      <FilterBuilderProperty v-model:property="filter.property" v-model:type="filter.type" :object="filter.object" />
    </template>
    <template v-else>
      <FilterBuilderValue v-model:type="filter.type" v-model:operation="filter.operation" v-model:value="filter.value" :property="filter.property" />
    </template>
    <template v-if="isCompleteFilter(filter)">
      <FilterTag class="filter-builder__tag" :filter="filter" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, reactive } from 'vue'
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
    (event: 'remove'): void,
  }>()

  const filter = reactive<Partial<Filter>>({})

  const hasObject = computed<boolean>(() => !!filter.object)
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