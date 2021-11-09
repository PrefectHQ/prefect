<template>
  <div ref="container" class="interval-bar-chart">
    <template v-if="items.length">
      <svg class="interval-bar-chart__svg" :id="id" ref="chart"></svg>

      <div class="interval-bar-chart__median" />

      <div class="interval-bar-chart__bucket-container">
        <template v-for="item in itemsWithValue" :key="item.interval_start">
          <Popover
            class="interval-bar-chart__popover"
            position="bottom"
            :style="calculateBucketPosition(item)"
          >
            <template v-slot:trigger="{ open, close }">
              <div
                class="interval-bar-chart__bucket"
                tabindex="0"
                @mouseenter="open"
                @mouseleave="close"
              />
            </template>
            <template v-slot:header>
              <div class="interval-bar-chart__popover-header">
                <slot name="popover-header" v-bind="item">
                  <span>{{ title }}</span>
                </slot>
              </div>
            </template>
            <template v-slot:default>
              <div class="interval-bar-chart__popover-content">
                <slot name="popover-content" v-bind="item">
                  <table>
                    <tr>
                      <td>Start Time:</td>
                      <td>
                        {{ formatDateTimeNumeric(item.interval_start) }}
                      </td>
                    </tr>
                    <tr>
                      <td>End Time:</td>
                      <td>
                        {{ formatDateTimeNumeric(item.interval_end) }}
                      </td>
                    </tr>
                    <tr>
                      <td>Value:</td>
                      <td>{{ item.value }}</td>
                    </tr>
                  </table>
                </slot>
              </div>
            </template>
          </Popover>
        </template>
      </div>
    </template>
    <template v-else>
      <slot name="empty">
        <div class="font--secondary subheader interval-bar-chart__empty">
          --
        </div>
      </slot>
    </template>
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'
import { IntervalBarChartItem } from './Types/IntervalBarChartItem'
import { CSSProperties } from '@vue/runtime-dom'
import { formatDateTimeNumeric } from '@/utilities/date'

class Props {
  intervalSeconds = prop<number>({ required: true })
  intervalStart = prop<Date>({ required: true })
  intervalEnd = prop<Date>({ required: true })
  backgroundColor = prop<string>({ required: false, default: null })
  items = prop<IntervalBarChartItem[]>({ required: true })
  title = prop<string>({ default: 'Details' })
}

@Options({})
export default class BarChart extends mixins(D3Base).with(Props) {
  formatDateTimeNumeric = formatDateTimeNumeric

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
    const values = this.items.map((item) => item.value)

    return Math.max(...values)
  }

  get barWidth(): number {
    return Math.floor(
      Math.min(10, (this.width - this.paddingX) / this.items.length / 2)
    )
  }

  get itemsWithValue(): IntervalBarChartItem[] {
    return this.items.filter((item) => item.value)
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

  calculateBucketPosition(item: IntervalBarChartItem): CSSProperties {
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

.interval-bar-chart__popover {
  position: absolute;
  transform: translateX(50%);
}

.interval-bar-chart__bucket {
  background-color: $grey-40;
  border-radius: 999px;
  transition: all 150ms;
  transform-origin: bottom;
  z-index: 1;
  width: inherit;
  height: inherit;

  &:hover,
  &:focus {
    background-color: $primary;
  }
}

.interval-bar-chart__popover-header {
  font-size: 18px;
}

.interval-bar-chart__popover-content {
  font-size: 14px;
}

.interval-bar-chart__empty {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>
