<template>
  <div class="filter-builder">
    <div class="filter-builder__header">
      <FilterBuilderHeading :filter="filter" />
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
  import { reactive } from 'vue'
  import { Filter } from '../types/filters'
  import { isCompleteFilter } from '../utilities/filters'
  import FilterBuilderHeading from './FilterBuilderHeading.vue'
  import FilterBuilderObject from './FilterBuilderObject.vue'
  import FilterBuilderProperty from './FilterBuilderProperty.vue'
  import FilterBuilderValue from './FilterBuilderValue.vue'
  import FilterTag from './FilterTag.vue'

  const filter = reactive<Partial<Filter>>({})
</script>

<style lang="scss" scoped>
.filter-builder {
  background-color: #fff;
  padding: var(--p-1) var(--p-2);
}

.filter-builder__tag {
  margin-top: var(--m-1);
}
</style>