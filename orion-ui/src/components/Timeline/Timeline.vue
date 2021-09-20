<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" class="timeline-chart" />

    <div class="node-container">
      <div
        v-for="item in computedItems"
        :key="item.id"
        class="node correct-text"
        :class="[item.state.toLowerCase() + '-bg']"
        :style="item.style"
        tabindex="0"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'
import { intervals } from '@/util/util'

interface Item {
  id: string
  name: string
  upstream_ids: string[]
  state: string
  tags: string[]
  start_time: string
  end_time: string
  style: {
    left: string
    top: string
    width: string
  }
}

const capR = 2

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

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>

class Props {
  backgroundColor = prop<string>({ required: false, default: null })
  interval = prop<string>({ required: false, default: 'minute' })
  items = prop<Item[]>({ required: true })
  padding = prop<{
    top: Number
    bottom: Number
    middle: Number
    left: Number
    right: Number
  }>({
    required: false,
    default: {
      top: 0,
      bottom: 0,
      middle: 0,
      left: 0,
      right: 0
    }
  })
}

@Options({
  watch: {
    items() {
      this.update()
    },
    interval() {
      this.update()
    }
  }
})
export default class Timeline extends mixins(D3Base).with(Props) {
  computedItems: Item[] = []
  intervalHeight: number = 24
  intervalWidth: number = 125
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  gridSelection: SelectionType = null as unknown as d3.Selection<
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

  get numberIntervals(): number {
    return Math.ceil(
      Math.max(
        this.totalSeconds / intervals[this.interval],
        this.width / this.intervalWidth
      )
    )
  }

  get numberRows(): number {
    return Math.ceil(
      Math.max(this.sortedItems.length, this.height / this.intervalHeight)
    )
  }

  get start(): Date {
    return new Date(
      new Date(
        Math.min(
          ...this.sortedItems.map((item) => new Date(item.start_time).getTime())
        )
      ).getTime() -
        intervals[this.interval] * 1000
    )
  }

  get end(): Date {
    return new Date(
      new Date(
        Math.max(
          ...this.sortedItems.map((item) => new Date(item.end_time).getTime())
        )
      ).getTime() +
        intervals[this.interval] * 1000
    )
  }

  get totalSeconds(): number {
    return this.end.getTime() / 1000 - this.start.getTime() / 1000
  }

  get chartHeight(): number {
    return (
      Math.max(this.numberRows * this.intervalHeight, this.height) -
      this.paddingY
    )
  }

  get chartWidth(): number {
    return (
      Math.max(this.numberIntervals * this.intervalWidth, this.width) -
      this.paddingY
    )
  }

  get sortedItems(): Item[] {
    return this.items
      .sort(
        (a, b) =>
          new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      )
      .filter((item: Item) => item.state !== 'PENDING' && item.start_time)
  }

  xAxis = (g: any) =>
    g
      .style('transform', `translate(0,${this.intervalHeight}px)`)
      .call(
        d3
          .axisTop(this.xScale)
          .ticks(this.numberIntervals)
          /* @ts-ignore */
          .tickFormat(formatLabel)
          .tickSizeOuter(0)
          .tickSizeInner(0)
      )
      /* @ts-ignore */
      .call((g) => g.select('.domain').remove())

  resize(): void {
    this.update()
  }

  mounted(): void {
    this.createChart()
    this.update()
  }

  update(): void {
    console.log('items', this.sortedItems)
    console.log('total seconds', this.totalSeconds)
    console.log('chart height', this.chartHeight)
    console.log('chart width', this.chartWidth)
    console.log('intervals', this.numberIntervals)
    console.log('rows', this.numberRows)
    console.log('start', this.start)
    console.log('end', this.end)
    this.updateScales()
    this.updateChart()
    this.updateGrid()
    this.updateNodes()
  }

  updated(): void {
    if (!this.svg || !this.gridSelection) this.createChart()
  }

  updateScales(): void {
    // Generate x scale
    this.xScale
      .domain([new Date(this.start), new Date(this.end)])
      .range([this.intervalWidth, this.chartWidth - this.intervalWidth])

    this.xAxisGroup.call(this.xAxis)
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.updateChart()

    this.svg
      .append('rect')
      .attr(
        'fill',
        this.backgroundColor ? `var(--${this.backgroundColor})` : 'transparent'
      )
      .attr('rx', 4)
      .attr('width', '100%')
      .attr('height', '100%')

    this.gridSelection = this.svg
      .append('g')
      .style('transform', `translate(0, 36px)`)

    this.xAxisGroup = this.svg.append('g')
  }

  updateChart(): void {
    this.svg
      .attr('viewbox', `0, 0, ${this.chartWidth}, ${this.chartHeight}`)
      .style('width', this.chartWidth + 'px')
      .style('height', this.chartHeight + 'px')
  }

  updateNodes(): void {
    this.computedItems = [...this.sortedItems].map((item: Item, i: number) => {
      const start = new Date(item.start_time)
      const end = new Date(item.end_time)
      return {
        ...item,
        style: {
          height: 8 + 'px',
          left: this.xScale(start) + 'px',
          top: i * this.intervalHeight + 'px',
          transform: `translate(0, ${this.intervalHeight + 18}px)`,
          width: this.xScale(end) - this.xScale(start) + 'px'
        }
      }
    })
  }

  updateGrid(): void {
    // TODO: Figure out what the heck the overloads for D3 are supposed to be...
    /* @ts-ignore */
    this.gridSelection
      .selectAll('.grid-line.grid-x')
      .data(Array.from({ length: this.numberRows }))
      .join(
        (selection: any) =>
          selection
            .append('line')
            .attr('class', 'grid-line grid-x')
            .attr('stroke', 'var(--blue-20)')
            .attr('x1', 0)
            .attr('x2', this.chartWidth)
            .attr('y1', (d: any, i: number) => i * this.intervalHeight)
            .attr('y2', (d: any, i: number) => i * this.intervalHeight),
        (selection: any) =>
          selection
            .attr('x1', 0)
            .attr('x2', this.chartWidth)
            .attr('y1', (d: any, i: number) => i * this.intervalHeight)
            .attr('y2', (d: any, i: number) => i * this.intervalHeight),
        (selection: any) => selection.remove()
      )

    /* @ts-ignore */
    this.gridSelection
      .selectAll('.grid-line.grid-y')
      .data(this.xScale.ticks())
      .join(
        (selection: any) =>
          selection
            .append('line')
            .attr('id', (d: any, i: number) => `x-${i}`)
            .attr('class', 'grid-line grid-y')
            .attr('stroke', 'var(--blue-20)')
            .attr('x1', (d: any, i: number) => this.xScale(d))
            .attr('x2', (d: any, i: number) => this.xScale(d))
            .attr('y1', 0)
            .attr('y2', this.chartHeight),
        (selection: any) =>
          selection
            .attr('x1', (d: any, i: number) => this.xScale(d))
            .attr('x2', (d: any, i: number) => this.xScale(d))
            .attr('y1', 0)
            .attr('y2', this.chartHeight),
        (selection: any) => selection.remove()
      )
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/timeline--chart.scss';
</style>

<style lang="scss">
.timeline-chart {
  .tick {
    font-size: 13px;
    font-family: $font--secondary;

    &:first-of-type {
      //   text-anchor: start;
    }

    &:last-of-type {
      //   text-anchor: end;
    }
  }
}
</style>
