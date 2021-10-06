<template>
  <Card class="schematic d-flex flex-column" width="auto" shadow="sm">
    <div class="schematic-content pa-2 d-flex flex-grow-1">
      <!-- <div
        style="
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          position: absolute;
        "
        class="text-center d-flex align-center"
      >
        <i class="pi pi-tools-fill pi-2x" />
        <h1 class="mx-2">Under construction</h1>
        <i class="pi pi-tools-fill pi-2x" />
      </div> -->
      <Schematic :items="items" />
    </div>
  </Card>
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
