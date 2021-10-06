<template>
  <div class="schematic z-0">
    <Schematic :items="items" />
  </div>
</template>

<script lang="ts" setup>
import { Api, Endpoints } from '@/plugins/api'
import { onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import Schematic from '@/components/Schematic/Schematic.vue'

const route = useRoute()
const items = ref([])

onBeforeMount(async () => {
  const query = Api.query({
    endpoint: Endpoints.schematic,
    body: {
      id: route?.params.id as string
    },
    options: {
      paused: true
    }
  })

  const res = await query.fetch()

  console.log(res)
  items.value = res.response.value
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/schematic.scss';
</style>
