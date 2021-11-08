<template>
  <div ref="container" class="interval-bar-chart">
    <svg class="interval-bar-chart__svg" :id="id" ref="chart"></svg>

    <div class="interval-bar-chart__median" />

    <div class="interval-bar-chart__bucket-container">
      <div
        v-for="item in items"
        :key="item.interval_start"
        class="interval-bar-chart__bucket"
        :style="calculateBucketPosition(item)"
        tabindex="0"
      >
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'

export interface Item {
  interval_start: string
  interval_end: string
  value: number
}
export type ItemCollection = Item[]

class Props {
  intervalSeconds = prop<number>({ required: true })
  intervalStart = prop<Date>({ required: true })
  intervalEnd = prop<Date>({ required: true })
  backgroundColor = prop<string>({ required: false, default: null })
  items = prop<ItemCollection>({ required: true })
}

@Options({})
export default class BarChart extends mixins(D3Base).with(Props) {
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  padding = {
    top: 16,
    bottom: 4,
    middle: 0,
    left: 0,
    right: 0
  }

  get maxValue(): number {
    return Math.max.apply(
      null,
      this.items.map((item: Item) => item.value)
    )
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.svg.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)
  }

  updateScales(): void {
    // Generate x scale
    const start = this.intervalStart
    const end = this.intervalEnd

    this.xScale
      .domain([start, end])
      .range([this.padding.left, this.width - this.paddingX])

    // Generate y scale
    this.yScale
      .domain([0, this.maxValue || 1])
      .range([0, this.height - this.paddingY])
  }

  get barWidth(): number {
    return Math.floor(
      Math.min(10, (this.width - this.paddingX) / this.items.length / 2)
    )
  }

  calculateBucketPosition(item: Item): { [key: string]: string } {
    const height = this.yScale(item.value)
    const top = this.height - this.padding.bottom - height
    const left = this.xScale(new Date(item.interval_start)) + this.padding.left

    return {
      height: `${height}px`,
      left: `${left}px`,
      top: `${top}px`,
      width: `${this.barWidth}px`
    }
  }

  resize(): void {
    this.svg.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)
    this.updateScales()
  }

  mounted(): void {
    this.createChart()
    this.updateScales()
  }

  beforeUpdate(): void {
    if (!this.svg) this.createChart()
    this.updateScales()
  }
}
</script>

<style lang="scss">
@use '@/styles/abstracts/variables';

.interval-bar-chart {
  height: 100%;
  position: relative;
  width: 100%;
}

.interval-bar-chart__svg {
  height: 100%;
  width: 100%;
}

.interval-bar-chart__median {
  height: 1px;
  background-color: $blue-20;
  position: absolute;
  left: 0;
  bottom: 0;
  transition: top 150ms;
  width: 100%;
}

.interval-bar-chart__bucket-container {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  height: 100%;
  width: 100%;
}

.interval-bar-chart__bucket {
  $r: 999px;
  background-color: $grey-40;
  border-radius: $r;
  position: absolute;
  transition: all 150ms;
  transform-origin: bottom;
  transform: translateX(50%);
  z-index: 1;

  &:hover,
  &:focus {
    background-color: $primary;
  }
}
</style>
