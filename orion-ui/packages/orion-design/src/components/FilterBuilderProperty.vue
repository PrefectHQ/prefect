<template>
  <div class="filter-builder-property-flow">
    <template v-for="objectProperty in objectProperties" :key="objectProperty">
      <m-button color="secondary" miter icon="pi-add-fill" @click="update(objectProperty.property, objectProperty.type)">
        {{ objectProperty.label }}
      </m-button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { FilterObject, FilterProperty, FilterType } from '../types/filters'

  const emit = defineEmits<{
    (event: 'update:property', value: FilterProperty): void,
    (event: 'update:type', value: FilterType): void,
  }>()

  const props = defineProps<{
    object: FilterObject,
    // prop used for v-model:property but not used internally
    // eslint-disable-next-line vue/no-unused-properties
    property?: FilterProperty,
    // prop used for v-model:property but not used internally
    // eslint-disable-next-line vue/no-unused-properties
    type?: FilterType,
  }>()

  type item = {
    objects: FilterObject[],
    property: FilterProperty,
    label: string,
    type?: FilterType,
  }

  const properties: item[] = [
    {
      property: 'name',
      label: 'Name',
      type: 'string',
      objects: ['flow', 'deployment', 'flow_run', 'task_run', 'tag'],
    },
    {
      property: 'state',
      label: 'Run state',
      type: 'state',
      objects: ['flow_run', 'task_run'],
    },
    {
      property: 'start_date',
      label: 'Start time',
      objects: ['flow_run', 'task_run'],
    },
    {
      property: 'tag',
      label: 'Tag',
      type: 'tag',
      objects: ['flow', 'deployment', 'flow_run', 'task_run'],
    },
  ]

  const objectProperties = computed(() => {
    return properties.filter(item => item.objects.includes(props.object))
  })

  function update(property: FilterProperty, type?: FilterType): void {
    emit('update:property', property)

    if (type) {
      emit('update:type', type)
    }
  }
</script>

<style lang="scss" scoped>
.filter-builder-property-flow {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-1);
}
</style>