<template>
  <div ref="container" class="run-history-chart">
    <svg :id="id" ref="chart" class="run-history-chart__chart"></svg>

    <div class="run-history-chart__median" :style="medianPosition" />

    <div class="run-history-chart__buckets">
      <div
        v-for="(item, i) in items"
        :key="item.interval_start"
        class="run-history-chart__bucket"
        :style="calculateBucketPosition(item)"
      >
        <template v-for="state in item.states" :key="state.state_type">
          <Popover
            :placement="['bottom', 'top', 'leftTop', 'rightTop']"
            :style="calculateBarPosition(state, i)"
            class="run-history-chart__popover"
          >
            <template v-slot:trigger="{ open, close }">
              <div
                class="run-history-chart__bar"
                :class="calculateBarClass(state)"
                :style="styles.bar"
                tabindex="0"
                @mouseenter="open"
                @mouseleave="close"
              />
            </template>
            <template v-slot:header>
              <div class="interval-bar-chart-card__popover-header">
                <i
                  class="
                    interval-bar-chart-card__popover-icon
                    pi pi-bar-chart-box-line pi-1
                    mr-1
                  "
                />
                Flow Activity
              </div>
            </template>
            <table class="table table--data">
              <tr>
                <td>Start Time:</td>
                <td>{{ formatDateTimeNumeric(item.interval_start) }}</td>
              </tr>
              <tr>
                <td>End Time:</td>
                <td>{{ formatDateTimeNumeric(item.interval_end) }}</td>
              </tr>
              <tr>
                <td>{{ state.state_name }}:</td>
                <td>{{ state.count_runs }}</td>
              </tr>
            </table>
          </Popover>
        </template>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'

import { Series } from 'd3-shape'
import { Selection } from 'd3-selection'
import { Transition } from 'd3-transition'
import { AxisDomain } from 'd3-axis'
import { Bucket, Buckets, StateBucket } from '@/typings/run_history'
import { StyleValue } from '@vue/runtime-dom'
import { ClassValue } from '@/types/css'

import { formatDateTimeNumeric } from '@/utilities/dates'

type TransitionSelectionType = Transition<
  SVGGElement,
  unknown,
  HTMLElement,
  null
>
type GroupSelectionType = Selection<SVGGElement, unknown, HTMLElement, null>

type BucketSeries = Series<Bucket, string>
type SeriesCollection = BucketSeries[]

const positiveStates: string[] = [
  'COMPLETED',
  'RUNNING',
  'SCHEDULED',
  'PENDING'
]
const mappedPositiveStates: [string, number][] = positiveStates.map(
  (d: string) => [d, -1]
)

const negativeStates: string[] = ['FAILED', 'CANCELLED']
const mappedNegativeStates: [string, number][] = negativeStates.map(
  (d: string) => [d, +1]
)

const directions: Map<string, number> = new Map([
  ...mappedPositiveStates,
  ...mappedNegativeStates
])

const formatMillisecond = d3.timeFormat('.%L'),
  formatSecond = d3.timeFormat(':%S'),
  formatMinute = d3.timeFormat('%I:%M'),
  formatHour = d3.timeFormat('%I %p'),
  formatDay = d3.timeFormat('%a %d'),
  formatWeek = d3.timeFormat('%b %d'),
  formatMonth = d3.timeFormat('%B'),
  formatYear = d3.timeFormat('%Y')

const formatLabel = (date: AxisDomain): string => {
  if (!(date instanceof Date)) return ''
  return (
    d3.timeSecond(date) < date
      ? formatMillisecond
      : d3.timeMinute(date) < date
      ? formatSecond
      : d3.timeHour(date) < date
      ? formatMinute
      : d3.timeDay(date) < date
      ? formatHour
      : d3.timeMonth(date) < date
      ? d3.timeWeek(date) < date
        ? formatDay
        : formatWeek
      : d3.timeYear(date) < date
      ? formatMonth
      : formatYear
  )(date)
}

class Props {
  intervalSeconds = prop<number>({ required: true })
  intervalStart = prop<Date>({ required: true })
  intervalEnd = prop<Date>({ required: true })
  backgroundColor = prop<string>({ required: false, default: null })
  items = prop<Buckets>({ required: true })
  showAxis = prop<boolean>({ required: false, default: false, type: Boolean })
  staticMedian = prop<boolean>({
    required: false,
    type: Boolean,
    default: false
  })
  padding = prop<{
    top: number
    bottom: number
    middle: number
    left: number
    right: number
  }>({
    required: false,
    default: {
      top: 12,
      bottom: 12,
      middle: 8,
      left: 16,
      right: 16
    }
  })
}

@Options({})
export default class RunHistoryChart extends mixins(D3Base).with(Props) {
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  formatDateTimeNumeric = formatDateTimeNumeric

  xAxisGroup: GroupSelectionType | undefined

  axisHeight = 20

  xAxis = (
    g: GroupSelectionType
  ): GroupSelectionType | TransitionSelectionType =>
    g
      .attr('transform', `translate(0,${this.height})`)
      .attr('class', 'caption')
      .transition()
      .duration(150)
      .call(
        d3
          .axisTop(this.xScale)
          .tickPadding(0)
          .tickFormat(formatLabel)
          .tickSizeInner(0)
          .tickSizeOuter(0)
      )
      .call((g) => g.select('.domain').remove())

  get series(): SeriesCollection {
    return (
      d3
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .stack<any, Bucket, string>()
        .keys([...positiveStates.slice().reverse(), ...negativeStates])
        .value(
          (d: Bucket, key: string) =>
            (directions.get(key) || 1) *
            (d.states.find((state) => state.state_type == key)?.count_runs || 0)
        )
        .offset(d3.stackOffsetDiverging)(this.items)
    )
  }

  get seriesMap(): Map<string, BucketSeries> {
    return new Map(this.series.map((s) => [s.key, s]))
  }

  get barWidth(): number {
    return Math.floor(
      Math.min(10, (this.width - this.paddingX) / this.items.length / 2)
    )
  }

  get viewHeight(): number {
    return this.height - this.axisHeight
  }

  get styles() {
    return {
      bar: {
        width: `${this.barWidth}px`
      }
    }
  }

  calculateBucketPosition(item: Bucket): StyleValue {
    return {
      left: this.xScale(new Date(item.interval_start)) + 'px'
    }
  }

  calculateBarPosition(item: StateBucket, bucketKey: number): StyleValue {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const series = this.seriesMap.get(item.state_type)!
    const seriesSlot = series[bucketKey]
    const height = this.yScale(seriesSlot[1]) - this.yScale(seriesSlot[0])
    const middle = this.padding.middle / 2
    const middleOffset = this.padding.middle
      ? // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        directions.get(item.state_type)! > 0
        ? middle
        : middle * -1
      : 0

    const top = this.yScale(seriesSlot[0]) + middleOffset

    return {
      height: `${height}px`,
      top: top + this.padding.top + this.padding.middle / 2 + 'px'
    }
  }

  calculateBarClass(item: StateBucket): ClassValue {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const direction = directions.get(item.state_type)!

    return [
      `${item.state_type.toLowerCase()}-bg`,
      {
        up: direction < 0,
        down: direction > 0
      }
    ]
  }

  median: number = -2

  updateMedian(): void {
    this.median = this.yScale(0) + this.padding.middle / 2
  }

  get medianPosition(): StyleValue {
    const top =
      (this.median > 0 ? this.median : this.height / 2) + this.padding.top

    return {
      top: `${top}px`
    }
  }

  resize(): void {
    this.updateScales()
  }

  mounted(): void {
    this.createChart()
    this.updateScales()
  }

  beforeUpdate(): void {
    if (!this.svg) this.createChart()
    this.updateScales()
    this.updateMedian()
  }

  updateScales(): void {
    const start = this.intervalStart
    const end = this.intervalEnd

    this.xScale
      .domain([start, end])
      .range([this.padding.left, this.width - this.padding.right])

    const flattened = this.series.flat(2)
    let min = Math.min(...flattened)
    let max = Math.max(...flattened)

    if (min == max) {
      min = -1
      max = 1
    }

    if (this.staticMedian) {
      const startMin = Math.abs(min) > Math.abs(max)
      const startEqual = Math.abs(min) === Math.abs(max)
      this.yScale
        // This can be used to keep a consistent middle line
        // otherwise the chart median will move with the data
        .domain([
          startMin || startEqual ? min : 0,
          startMin || startEqual ? 0 : max
        ])
        .range([0, this.viewHeight - this.paddingY])
    } else {
      this.yScale.domain([min, max]).range([0, this.viewHeight - this.paddingY])
    }

    if (this.showAxis && this.xAxisGroup) {
      this.xAxisGroup.call(this.xAxis)
    }
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.svg.attr('viewbox', `0, 0, ${this.width}, ${this.height}`)

    this.svg
      .append('rect')
      .attr(
        'fill',
        this.backgroundColor ? `var(--${this.backgroundColor})` : 'transparent'
      )
      .attr('rx', 4)
      .attr('width', '100%')
      .attr('height', `${this.viewHeight}px`)

    this.xAxisGroup = this.svg.append('g')
  }
}
</script>

<style lang="scss">
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.run-history-chart {
  height: 100%;
  position: relative;
  overflow: hidden;
  width: 100%;
}

.run-history-chart__chart {
  width: 100%;
  height: 100%;

  .tick line {
    display: none;
  }
  .tick {
    &:first-of-type,
    &:last-of-type {
      display: none;
    }
  }
}

.run-history-chart__median {
  height: 1px;
  background-color: $blue-20;
  position: absolute;
  left: 0;
  top: -2;
  transition: top 150ms;
  width: 100%;
}

.run-history-chart__buckets {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  height: 100%;
  width: 100%;
}

.run-history-chart__bucket {
  position: absolute;
  transition: all 150ms;
}

.run-history-chart__popover {
  position: absolute;
}

.run-history-chart__bar {
  border-radius: 999px;
  height: inherit;
}
</style>
