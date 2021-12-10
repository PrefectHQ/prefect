<template>
  <MiniRadar :id="id" :radar="radar" hide-viewport disable-interactions />
</template>

<script lang="ts" setup>
import { Api, Endpoints, Query } from '@/plugins/api'
import { computed, watch, ref, onMounted } from 'vue'
import { Radar } from '@/components/Radar/Radar'
import MiniRadar from '@/components/Radar/MiniRadar.vue'

const radar = ref<Radar>(new Radar())
const props = defineProps<{ id: string }>()

const radarFilter = computed(() => {
  return {
    id: props.id
  }
})

const queries: { [key: string]: Query } = {
  radar: Api.query({
    endpoint: Endpoints.radar,
    body: radarFilter,
    options: {
      pollInterval: 5000
    }
  })
}

watch(
  () => queries.radar.response?.value,
  (val) => {
    if (val) {
      radar.value.items(val)
    }
  }
)

onMounted(() => {
  radar.value.id('id').dependencies('upstream_dependencies').items([])
})
</script>
