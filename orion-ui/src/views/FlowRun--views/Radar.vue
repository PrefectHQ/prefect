<template>
  <div class="radar z-0">
    <Radar :items="items" />
  </div>
</template>

<script lang="ts" setup>
import { Api, Endpoints, Query } from '@/plugins/api'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Radar from '@/components/Radar/Radar.vue'

const route = useRoute()

const id = computed<string>(() => {
  return route?.params.id as string
})

const radarFilter = computed(() => {
  return {
    id: id.value
  }
})

const queries: { [key: string]: Query } = {
  radar: Api.query({
    endpoint: Endpoints.radar,
    body: radarFilter.value,
    options: {
      // pollInterval: 5000
    }
  })
}

const items = computed<[]>(() => {
  return queries.radar.response?.value || []
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/radar.scss';
</style>
