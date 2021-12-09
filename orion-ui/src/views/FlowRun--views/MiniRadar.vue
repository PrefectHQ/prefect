<template>
  <div ref="container">
    <MiniRadar :id="id" :radar="radar" hide-viewport disable-interactions />
  </div>
</template>

<script lang="ts" setup>
import { Api, Endpoints, Query } from '@/plugins/api'
import { computed, watch, ref, onMounted, onUnmounted } from 'vue'
import { Radar } from '@/components/Radar/Radar'
import MiniRadar from '@/components/Radar/MiniRadar.vue'

const radar = ref<Radar>(new Radar())
const props = defineProps<{ id: string }>()

const container = ref<HTMLElement>()
const height = ref<number>(0)
const width = ref<number>(0)

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

const handleWindowResize = (): void => {
  if (!container.value) return
  height.value = container.value.offsetHeight
  width.value = container.value.offsetWidth
}

onMounted(() => {
  handleWindowResize()
  window.addEventListener('resize', handleWindowResize)
  radar.value
    .id('id')
    .dependencies('upstream_dependencies')
    .center([width.value / 2, height.value / 2])
    .items([])
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})
</script>
