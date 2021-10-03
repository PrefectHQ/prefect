<template>
  <Card class="schematic d-flex flex-column" width="auto" shadow="sm">
    <div class="schematic-content pa-2 d-flex flex-grow-1">
      <div
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
      </div>
    </div>
  </Card>
</template>

<script lang="ts" setup>
// import { Api, Query, Endpoints, BaseFilter } from '@/plugins/api'
// import { TaskRun } from '@/typings/objects'
// import { computed, ref } from 'vue'
// import { useRoute } from 'vue-router'
// import Schematic from '@/components/Schematic/Schematic.vue'

// const route = useRoute()

// const schematic = ref<InstanceType<typeof Schematic>>()
// const search = ref<string>('')

// const id: string = route.params.id as string

// const taskRunsFilter = computed<BaseFilter>(() => {
//   return {
//     flow_runs: {
//       id: {
//         any_: [id]
//       }
//     }
//   }
// })

// const TaskRunCountQuery = Api.query({
//     endpoint: Endpoints.task_runs_count,
//     body: taskRunsFilter,
//     options: {
//       pollInterval: 10000
//     }
//   }),

// const queries: { [key: string]: Query } = {
//   task_runs: Api.query({
//     endpoint: Endpoints.task_runs,
//     body: taskRunsFilter,
//   })
// }
// const taskRuns = computed<TaskRun[]>(() => {
//   return queries.task_runs.response?.value || []
// })

// console.log(queries.task_runs)

// const handleSelectSearchOption = (item: any): void => {
//   if (!item) return
//   search.value = item.name
//   ;(schematic as unknown as InstanceType<typeof Schematic>)?.panToNode(item)
// }
// const route = useRoute()

// const flowRunBase: Query = await Api.query({
//   endpoint: Endpoints.flow_run,
//   body: {
//     id: route.params.id as string
//   },
//   options: {
//     pollInterval: 5000
//   }
// }).fetch()

// const taskRunsFilter = computed<BaseFilter>(() => {
//   return {
//     flow_runs: {
//       id: {
//         any_: [route.params.id as string]
//       }
//     }
//   }
// })

// const queries: { [key: string]: Query } = {
//   task_runs: Api.query({
//     endpoint: Endpoints.task_runs,
//     body: taskRunsFilter,
//     options: {
//       pollInterval: 10000
//     }
//   })
// }

// const flowRun = computed<FlowRun>(() => {
//   return flowRunBase.response?.value || {}
// })

// const end = computed<string>(() => {
//   return flowRun.value.end_time
// })
// const taskRuns = computed<TaskRun[]>(() => {
//   return queries.task_runs.response?.value || []
// })

// // This cleanup is necessary since the initial flow run query isn't
// // wrapped in the queries object
// onBeforeUnmount(() => {
//   flowRunBase.stopPolling()
//   Api.queries.delete(flowRunBase.id)
// })
</script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/schematic.scss';
</style>
