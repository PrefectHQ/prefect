<template>
  <list-item class="list-item--flow d-flex align-start justify-start">
    <i class="item--icon pi pi-flow text--grey-40 align-self-start" />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ item.name }}
      </h2>

      <div class="nowrap tag-container d-flex align-bottom">
        <Tag
          v-for="tag in item.tags"
          :key="tag"
          color="secondary-pressed"
          class="caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto nowrap">
      <rounded-button class="mr-1">
        {{ flowRunCount }} flow run{{ flowRunCount === 1 ? '' : 's' }}
      </rounded-button>

      <rounded-button class="mr-1">
        {{ taskRunCount }} task run{{ taskRunCount === 1 ? '' : 's' }}
      </rounded-button>
    </div>

    <div v-breakpoints="'md'" class="chart-container">
      <!-- <RunHistoryChart
        v-if="false"
        :items="taskRunBuckets"
        :padding="{ top: 3, bottom: 3, left: 0, right: 0, middle: 8 }"
      /> -->
    </div>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Flow } from '@/typings/objects'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'

import { Api, Query, Endpoints } from '@/plugins/api'
import { Bucket } from '@/typings/run_history'

class Props {
  item = prop<Flow>({ required: true })
}

@Options({ components: { RunHistoryChart } })
export default class ListItemFlow extends Vue.with(Props) {
  queries: { [key: string]: Query } = {
    // flow_run_history: Api.query({
    //   endpoint: Endpoints.flow_runs_history,
    //   body: {}
    // }),
    flow_run_count: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: {
        flows: {
          id: {
            any_: [this.item.id]
          }
        }
      }
    }),
    task_run_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: {
        flows: {
          id: {
            any_: [this.item.id]
          }
        }
      }
    })
  }

  taskRunBuckets: Bucket[] = []

  get flowRunCount(): number {
    console.log(this.queries.flow_run_count.response)
    return this.queries.flow_run_count.response || 0
  }

  get taskRunCount(): number {
    return this.queries.task_run_count.response || 0
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow.scss';
</style>
