<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" />
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'

export interface Item {
  value: number
}
export type ItemCollection = Item[]

class Props {
  backgroundColor = prop<String>({ required: false, default: null })
  items = prop<ItemCollection>({ required: true })
  showAxis = prop<Boolean>({ required: false, default: false, type: Boolean })
}

@Options({
  // props: {
  //   backgroundColor: {
  //     type: String,
  //     required: false,
  //     default: null
  //   },
  //   items: {
  //     type: [] as PropType<BucketCollection>,
  //     required: true
  //   },
  //   showAxis: {
  //     type: Boolean,
  //     required: false,
  //     default: false
  //   }
  // }
})
export default class RunHistoryChart extends mixins(D3Base).with(Props) {
  padding = {
    top: 12,
    bottom: 12,
    middle: 12,
    left: 16,
    right: 16
  }

  mounted(): void {
    console.log(this.id)
  }
}
</script>

<style lang="scss">
@use '@/styles/components/bar--chart.scss';
</style>
