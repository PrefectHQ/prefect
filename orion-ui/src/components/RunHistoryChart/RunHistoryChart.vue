<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" class="run-history-chart" />
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'

import { createCappedBar } from '@/components/Visualizations/utils'

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

const capR = 2

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

const formatLabel = (date: Date) => {
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

export interface StateAggregate {
  [key: string]: number
}

export interface Bucket {
  interval_start: Date
  interval_end: Date
  states: StateAggregate
}
export type BucketCollection = Bucket[]

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>

class Props {
  backgroundColor = prop<String>({ required: false, default: null })
  items = prop<Bucket[]>({ required: true })
  showAxis = prop<Boolean>({ required: false, default: false, type: Boolean })
  padding = prop<{
    top: Number
    bottom: Number
    middle: Number
    left: Number
    right: Number
  }>({
    required: false,
    default: {
      top: 12,
      bottom: 12,
      middle: 12,
      left: 16,
      right: 16
    }
  })
}

@Options({})
export default class RunHistoryChart extends mixins(D3Base).with(Props) {
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  barSelection: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  xAxisGroup: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  xAxis = (g: any) =>
    g
      .attr('transform', `translate(0,${this.height})`)
      .call(
        d3
          .axisTop(this.xScale)
          .ticks(this.width / 100)
          /* @ts-ignore */
          .tickFormat(formatLabel)
          .tickSizeOuter(0)
      )
      /* @ts-ignore */
      .call((g) => g.select('.domain').remove())

  get buckets(): Bucket[] {
    return this.items.map((d: Bucket) => {
      const states: { [key: string]: number } = {}
      Object.entries(d.states).forEach(([state, count]) => {
        states[state] = count * (state == 'FAILED' ? -1 : 1)
      })
      return { ...d, states }
    })
  }

  get series(): any {
    return (
      d3
        .stack()
        .keys([...positiveStates.slice().reverse(), ...negativeStates])
        .value(
          /* @ts-ignore */
          (d, key: string) => (directions.get(key) || 1) * (d.states[key] || 0)
        )
        /* @ts-ignore */
        .offset(d3.stackOffsetDiverging)(this.items)
    )
  }

  get seriesMap(): Map<string, []> {
    return new Map(this.series.map((s: any) => [s.key, s]))
  }

  resize(): void {
    this.updateScales()
    this.updateBuckets()
  }

  mounted(): void {
    this.createChart()
    this.updateScales()
    this.updateBuckets()
  }

  updated(): void {
    if (!this.svg || !this.barSelection) this.createChart()
    this.updateScales()
    this.updateBuckets()
  }

  updateScales(): void {
    const start = this.items[0].interval_start
    const end = this.items[this.items.length - 1].interval_end
    this.xScale.domain([new Date(start), new Date(end)]).range([0, this.width])

    const flattened = this.series.flat(2)
    const min = Math.min(...flattened)
    const max = Math.max(...flattened)
    const startMin = Math.abs(min) > Math.abs(max)

    this.yScale
      .domain([startMin ? min : 0, startMin ? 0 : max])
      .rangeRound([
        this.padding.top,
        this.height / 2 - this.padding.bottom - this.padding.middle
      ])

    if (this.showAxis) {
      this.xAxisGroup.call(this.xAxis)
    }
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.svg.attr(
      'viewbox',
      `0, 0, ${this.width - this.paddingX}, ${this.height - this.paddingY}`
    )

    this.svg
      .append('rect')
      .attr(
        'fill',
        this.backgroundColor ? `var(--${this.backgroundColor})` : 'transparent'
      )
      .attr('rx', 4)
      .attr('width', '100%')
      .attr(
        'height',
        `${
          this.height -
          this.padding.top -
          this.padding.bottom -
          this.padding.middle
        }px`
      )

    this.barSelection = this.svg.append('g')

    this.xAxisGroup = this.svg.append('g')

    // TODO: Remove this guidelines (for tesitng purposes only)
    // this.svg
    //   .append('line')
    //   .attr('x1', 0)
    //   .attr('x2', this.width)
    //   .attr('y1', this.height / 2 + this.padding.middle / 2)
    //   .attr('y2', this.height / 2 + this.padding.middle / 2)
    //   .attr('stroke-width', this.padding.middle / 6)
    //   .attr('stroke-dasharray', 12)
    //   .attr('stroke', 'rgba(0, 0, 0, 0.03')
  }

  updateBarPath(d: any, i: number): string | void {
    const maxWidth = this.width / this.items.length / 2
    const seriesSlot = this.seriesMap.get(d.state)![d.bucket_key]
    const biasIndex = directions.get(d.state)

    if (!seriesSlot || !biasIndex) return
    const items = this.items.find(
      /* @ts-ignore */
      (_d) => _d.interval_start == seriesSlot.data.interval_start
    )
    const states = items?.states || []
    const stateEntries = Object.entries(states)

    const arr = biasIndex > 0 ? negativeStates : positiveStates
    const stateIndex = arr.findIndex((s) => s == d.state)

    const otherStates = stateEntries.filter(
      ([state, count]) => state !== d.state && arr.includes(state)
    )
    const adjustedArr = arr.filter(
      (s) => stateEntries.find((_s) => _s[0] == s)?.[1] || 0 > 0
    )
    const sumCountOther = otherStates.reduce((acc, curr) => acc + curr[1], 0)

    /*
          Round both top and bottom corners if:
            - Is the only bar in the series

          Round top corners if:
            - Is the first bar in the positive series
            - Is the last bar in the negative series

          Round bottom corners if:
            - Is the last bar in the positive series
            - Is the first bar in the negative series
        */

    let showCapTop = false
    let showCapBottom = false

    if (sumCountOther == 0) {
      showCapTop = true
      showCapBottom = true
    } else if (biasIndex < 0) {
      if (stateIndex === adjustedArr.length - 1) showCapBottom = true
      if (stateIndex === 0) showCapTop = true
    } else if (biasIndex > 0) {
      if (stateIndex === adjustedArr.length - 1) showCapBottom = true
      if (stateIndex === 0) showCapTop = true
    }

    const width = Math.min(10, maxWidth) / 2

    const r = Math.min(capR, width / 2)

    const xStart =
      /* @ts-ignore */
      this.xScale(new Date(seriesSlot.data.interval_start)) + maxWidth / 2
    const yStart =
      this.yScale(seriesSlot[0]) +
      this.padding.top +
      (biasIndex > 0 ? this.padding.middle : 0) +
      (biasIndex < 0 ? r / 2 : 0)
    const height = this.yScale(seriesSlot[1]) - this.yScale(seriesSlot[0])

    if (height == 0) return ''

    return createCappedBar({
      capTop: showCapTop,
      capBottom: showCapBottom,
      x: xStart,
      y: yStart,
      height: height,
      width: width,
      radius: r
    })
  }

  updateBuckets(): void {
    if (!this.barSelection) return
    // TODO: Figure out what the heck the overloads for D3 are supposed to be...
    /* @ts-ignore */
    this.barSelection
      .selectAll('.bucket')
      .data(this.items, (d: any) => d.interval_start)
      .join(
        (enter: any) =>
          enter
            .append('g')
            .attr('class', 'bucket')
            .attr('id', (d: Bucket | any) => d.interval_start.toString())
            .style(
              'transform',
              `translate(${this.padding.left}px, ${this.padding.top}px)`
            ),
        (update: any) =>
          update.style(
            'transform',
            `translate(${this.padding.left}px, ${this.padding.top}px)`
          ),
        (exit: any) => exit.remove()
      )
      .selectAll('path')
      /* @ts-ignore */
      .data((d: Bucket, i: number) =>
        Object.entries(d.states).map(([state, count]) => {
          return { state: state, count: count, bucket_key: i }
        })
      )
      .join(
        (enter: any) =>
          enter /* @ts-ignore */
            .append('path')
            .attr('d', this.updateBarPath)
            .attr(
              'class',
              // TODO: Figure out what the heck the overloads for D3 are supposed to be...
              /* @ts-ignore */
              (d: any) => d.state.toLowerCase() + '-fill'
            ),
        (update: any) =>
          update.attr('d', this.updateBarPath).attr(
            'class',
            // TODO: Figure out what the heck the overloads for D3 are supposed to be...
            /* @ts-ignore */
            (d: any) => d.state.toLowerCase() + '-fill'
          ),
        (exit: any) => exit.remove()
      )
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/run-history--chart.scss';
</style>
