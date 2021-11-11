<template>
  <div class="schematic z-0">
    <Schematic :items="items" />
  </div>
</template>

<script lang="ts" setup>
import { Api, Endpoints, Query } from '@/plugins/api'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Schematic from '@/components/Schematic/Schematic.vue'

const route = useRoute()

const id = computed<string>(() => {
  return route?.params.id as string
})

const schematicFilter = computed<string>(() => {
  return {
    id: id.value
  }
})

const queries: { [key: string]: Query } = {
  schematic: Api.query({
    endpoint: Endpoints.schematic,
    body: schematicFilter,
    options: {
      // pollInterval: 5000
    }
  })
}

const items = computed<[]>(() => {
  return queries.schematic.response?.value || []
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/schematic.scss';
</style>
