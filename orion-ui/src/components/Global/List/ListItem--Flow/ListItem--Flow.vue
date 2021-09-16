<template>
  <list-item>
    <div>
      <i class="item--icon pi pi-flow pi-2x" />

      <div>
        <div class="item--title subheader">
          {{ flow.name }}
        </div>
        <Tag
          v-for="tag in flow.tags"
          :key="tag"
          color="secondary-pressed"
          class="item--tags mr-1"
          outlined
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div class="ml-auto chart-container mr-2">
      <RunHistoryChart :data="taskRunBuckets" />
    </div>
    <Button color="primary">Quick run</Button>
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
  taskRunBuckets: Bucket[] = dataset_2.slice(
    Math.floor(Math.random() * 4),
    Math.floor(Math.random() * 9 + 14)
  )
}
</script>

<style lang="scss" scoped>
.chart-container {
  max-width: 250px;
}
</style>
