<template>
  <list-item class="list-item--flow-run d-flex align-start justify-start">
    <i class="item--icon pi text--grey-40 align-self-start" :class="state" />
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
        {{ run.name }}
      </h2>

      <div class="tag-container nowrap d-flex align-bottom">
        <span
          class="run-state correct-text caption mr-1"
          :class="state + '-bg'"
        >
          {{ state }}
        </span>

        <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto nowrap">
      <rounded-button class="mr-1">
        {{ taskRunCount }} task runs
      </rounded-button>
    </div>

    <div v-breakpoints="'md'" class="chart-container mr-2">
      <RunHistoryChart
        :items="taskRunBuckets"
        :padding="{ top: 3, bottom: 3, left: 0, right: 0, middle: 8 }"
      />
    </div>

    <div class="font--secondary item--duration">
      {{ duration }}
    </div>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { FlowRun } from '@/objects'
import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

import { default as dataset_2 } from '@/util/run_history/design.json'

class Props {
  run = prop<FlowRun>({ required: true })
}

@Options({
  components: { RunHistoryChart }
})
export default class ListItemFlowRun extends Vue.with(Props) {
  taskRunCount: number = Math.floor(Math.random() * 100)
  sliceStart: number = Math.floor(Math.random() * 4)

  taskRunBuckets: Bucket[] = dataset_2.slice(
    this.sliceStart,
    this.sliceStart + 10
  )

  get state(): string {
    return this.run.state.toLowerCase()
  }

  get tags(): string[] {
    return this.run.tags
  }

  get reason(): string | null {
    return this.state == 'failed' ? 'Lorem ipsum dolorset atem' : null
  }

  get duration(): string {
    const durations = ['1m 3s', '4hr 23m', '--']
    return this.state == 'pending'
      ? durations[2]
      : this.state == 'running'
      ? durations[0]
      : durations[1]
  }
}
</script>

<style lang="scss" scoped>
.item--tags {
  border-radius: 4px;
  display: inline-block;
  padding: 4px 8px;
}

.run-state {
  text-transform: capitalize;
}
</style>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow-run.scss';
</style>
