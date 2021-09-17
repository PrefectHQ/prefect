<template>
  <list-item class="list-item--flow d-flex align-start justify-start">
    <i class="item--icon pi pi-flow text--grey-40 align-self-start" />

    <div class="ml-2 d-flex flex-column align-start justify-center">
      <h2 class="item--title subheader">
        {{ flow.name }}
      </h2>

      <div>
        <Tag
          v-for="tag in flow.tags"
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

    <rounded-button> {{ flowRunCount }} flow runs </rounded-button>

    <rounded-button> {{ taskRunCount }} task runs </rounded-button>

    <div class="ml-auto chart-container mr-2">
      <RunHistoryChart
        :items="taskRunBuckets"
        :padding="{ top: 3, bottom: 3, left: 0, right: 0, middle: 8 }"
      />
    </div>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Flow } from '@/objects'
import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

import { default as dataset_2 } from '@/util/run_history/design.json'

class Props {
  flow = prop<Flow>({ required: true })
}

@Options({ components: { RunHistoryChart } })
export default class ListItemFlow extends Vue.with(Props) {
  sliceStart: number = Math.floor(Math.random() * 4)

  taskRunBuckets: Bucket[] = dataset_2.slice(
    this.sliceStart,
    this.sliceStart + 10
  )

  flowRunCount: number = 25
  taskRunCount: number = 139
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow.scss';
</style>
