<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" class="run-history-chart"></svg>

    <div class="median" :style="medianPosition" />

    <div class="bar-container">
      <div
        v-for="(item, i) in items"
        :key="item.interval_start"
        class="interval-bucket"
        :style="calculateBucketPosition(item)"
      >
        <div class="up">
          <div
            v-for="state in item.states.filter((s) =>
              positiveStates.includes(s.state_type)
            )"
            :key="state.state_type"
            class="interval-bucket-state"
            :class="calculateBarClass(state)"
            :style="calculateBarPosition(state, i)"
            tabindex="0"
          >
          </div>
        </div>

        <div class="down">
          <div
            v-for="state in item.states.filter((s) =>
              negativeStates.includes(s.state_type)
            )"
            :key="state.state_type"
            class="interval-bucket-state"
            :class="calculateBarClass(state)"
            :style="calculateBarPosition(state, i)"
            tabindex="0"
          >
          </div>
        </div>
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

  xAxisGroup: GroupSelectionType | undefined

  positiveStates = positiveStates
  negativeStates = negativeStates

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
          // .tickArguments(d3.timeSecond.every(this.intervalSeconds))
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
      height: height + 'px',
      top: top + this.padding.top + this.padding.middle / 2 + 'px',
      transform: 'translate(-50%)',
      width: this.barWidth + 'px'
    }
  }

  calculateBarClass(item: StateBucket): { [key: string]: boolean } {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const direction = directions.get(item.state_type)!

    return {
      [`${item.state_type.toLowerCase()}-bg`]: true,
      up: direction < 0,
      down: direction > 0
    }
  }

  median: number = -2

  updateMedian(): void {
    this.median = this.yScale(0) + this.padding.middle / 2
  }

  get medianPosition(): StyleValue {
    const top =
      (this.median > 0 ? this.median : this.height / 2) + this.padding.top

    return {
      top: top + 'px'
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
    // console.log('items from bar chart', this.items, this.padding)
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
        .rangeRound([0, this.viewHeight - this.paddingY])
    } else {
      this.yScale
        .domain([min, max])
        .rangeRound([0, this.viewHeight - this.paddingY])
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

    // TODO: Remove this guidelines (for tesitng purposes only)
    // const viewMiddle = this.viewHeight / 2
    // this.svg
    //   .append('line')
    //   .attr('x1', 0)
    //   .attr('x2', this.width)
    //   .attr('y1', viewMiddle)
    //   .attr('y2', viewMiddle)
    //   .attr('stroke-width', 2)
    //   .attr('stroke-dasharray', 12)
    //   .attr('stroke', 'rgba(0, 0, 0, 0.03')
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/run-history--chart.scss';
</style>

<style lang="scss">
@use '@prefect/miter-design/src/styles/abstracts/variables' as *;

.run-history-chart {
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
</style>
