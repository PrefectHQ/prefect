<template>
  <div class="filter-builder-property-flow">
    <template v-for="objectProperty in objectProperties" :key="objectProperty">
      <m-button color="secondary" miter icon="pi-add-fill" @click="update(objectProperty)">
        {{ objectProperty.label }}
      </m-button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Filter, FilterObject, FilterProperty, FilterType } from '@/types/filters'

  const emit = defineEmits<{
    (event: 'update:filter', value: Partial<Filter>): void,
  }>()

  const props = defineProps<{
    filter: Partial<Filter>,
  }>()

  type item = {
    objects: FilterObject[],
    property: FilterProperty,
    label: string,
    type: FilterType,
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
      type: 'date',
      objects: ['flow_run', 'task_run'],
    },
    {
      property: 'tag',
      label: 'Tag',
      type: 'tag',
      objects: ['flow', 'deployment', 'flow_run', 'task_run'],
    },
  ]

  const filter = computed({
    get() {
      return props.filter
    },
    set(filter: Partial<Filter>) {
      emit('update:filter', filter)
    }
  })

  const objectProperties = computed(() => {
    return properties.filter(item => item.objects.includes(props.filter.object!))
  })

  function update(item: item): void {
    filter.value = { ...filter.value, property: item.property, type: item.type } as Partial<Filter>
  }
</script>

<style lang="scss">
.filter-builder-property-flow {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-1);
}
</style>