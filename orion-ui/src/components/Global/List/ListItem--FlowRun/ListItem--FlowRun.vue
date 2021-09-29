<template>
  <list-item class="list-item--flow-run d-flex align-start justify-start">
    <!-- For a later date... maybe -->
    <!-- :class="state + '-border'" -->

    <i
      class="item--icon pi text--grey-40 align-self-start"
      :class="`pi-${state}`"
    />
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
        v-if="false"
        :items="taskRunBuckets"
        :padding="{ top: 3, bottom: 3, left: 0, right: 0, middle: 8 }"
      />
    </div>

    <div class="font--secondary item--duration mr-2">
      {{ duration }}
    </div>

    <i class="pi pi-arrow-right-s-line text--grey-80" />
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { FlowRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'

import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

class Props {
  item = prop<FlowRun>({ required: true })
}

@Options({
  components: { RunHistoryChart }
})
export default class ListItemFlowRun extends Vue.with(Props) {
  sliceStart: number = Math.floor(Math.random() * 4)

  taskRunBuckets: Bucket[] = []

  get taskRunCount(): number {
    return this.item.task_run_count
  }

  get state(): string {
    return this.item.state.type.toLowerCase()
  }

  get tags(): string[] {
    return this.item.tags
  }

  get reason(): string | null {
    return this.state == 'failed' ? 'Lorem ipsum dolorset atem' : null
  }

  get duration(): string {
    return this.state == 'pending' || this.state == 'scheduled'
      ? '--'
      : this.item.total_run_time
      ? secondsToApproximateString(this.item.total_run_time)
      : secondsToApproximateString(this.item.estimated_run_time)
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
