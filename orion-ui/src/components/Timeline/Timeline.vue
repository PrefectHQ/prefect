<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" class="run-history-chart" />

    <div class="node-container">
      <div
        v-for="item in items"
        :key="item.id"
        class="node"
        :style="getNodePosition(item)"
      >
        {{ item.state }}{{ getNodePosition(item) }}
      </div>
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

@Options({})
export default class Timeline extends mixins(D3Base).with(Props) {
  intervalHeight: number = 24
  intervalWidth: number = 480
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  barSelection: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

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
    console.log(this.totalSeconds, intervals, intervals[this.interval])
    return this.totalSeconds / intervals[this.interval]
  }

  get numberRows(): number {
    return Math.max(this.items.length, this.height / this.intervalHeight)
  }

  get start(): Date {
    return new Date(this.items[0].start_time)
  }

  get end(): Date {
    return new Date(this.items[this.items.length - 1].end_time)
  }

  get totalSeconds(): number {
    return this.end.getTime() / 1000 - this.start.getTime() / 1000
  }

  get chartHeight(): number {
    return Math.max(this.numberRows * this.intervalHeight, this.height)
  }

  get chartWidth(): number {
    return this.numberIntervals * this.intervalWidth
  }

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

  resize(): void {
    this.update()
  }

  mounted(): void {
    console.log(this.items)
    this.createChart()
    this.update()
  }

  update(): void {
    this.updateScales()
    this.updateGrid()
    // this.updateBars()
  }

  updated(): void {
    if (!this.svg || !this.barSelection) this.createChart()
    this.update()
  }

  updateScales(): void {
    // Generate x scale
    this.xScale.domain([this.start, this.end]).range([0, this.chartWidth])
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.svg
      .attr(
        'viewbox',
        `0, 0, ${this.chartWidth - this.paddingX}, ${
          this.chartHeight - this.paddingY
        }`
      )
      .style('width', this.chartWidth - this.paddingX + 'px')
      .style('height', this.chartHeight - this.paddingY + 'px')

    this.svg
      .append('rect')
      .attr(
        'fill',
        this.backgroundColor ? `var(--${this.backgroundColor})` : 'transparent'
      )
      .attr('rx', 4)
      .attr('width', '100%')
      .attr('height', '100%')

    this.barSelection = this.svg.append('g')
    this.gridSelection = this.svg.append('g')

    this.xAxisGroup = this.svg.append('g')
  }

  getNodePosition(item: Item): { [key: string]: any } {
    return {
      left: this.xScale(new Date(item.start_time)) + 'px'
    }
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
            .attr(
              'y1',
              (d: any, i: number) =>
                i * this.intervalHeight + this.intervalHeight
            )
            .attr(
              'y2',
              (d: any, i: number) =>
                i * this.intervalHeight + this.intervalHeight
            ),
        () => {},
        () => {}
      )

    console.log(Array.from({ length: this.numberRows }, (x, i) => i))

    /* @ts-ignore */
    this.gridSelection
      .selectAll('.grid-line.grid-y')
      .data(Array.from({ length: this.numberRows }, (x, i) => i))
      .join(
        (selection: any) =>
          selection
            .append('line')
            .attr('class', 'grid-line grid-y')
            .attr('stroke', 'var(--blue-20)')
            .attr(
              'x1',
              (d: any, i: number) => i * this.intervalWidth + this.intervalWidth
            )
            .attr(
              'x2',
              (d: any, i: number) => i * this.intervalWidth + this.intervalWidth
            )
            .attr('y1', 0)
            .attr('y2', this.chartHeight),
        () => {},
        () => {}
      )
  }

  //   updateBars(): void {
  //     this.barSelection
  //       .selectAll('.bar')
  //       .data(this.items)
  //       .join((selection: any) =>
  //         selection
  //           .append('rect')
  //           .attr('class', (d: Item) => {
  //             return `bar ${d.state.toLowerCase()}-fill`
  //           })
  //           .attr('x', (d: Item, i: number) => 100)
  //           .attr('y', (d: Item, i: number) => i * 100 + 100)
  //           .attr('width', (d: Item, i: number) => 100)
  //           .attr('height', (d: Item, i: number) => 45)
  //       )
  //   }

  //   updateBarPath(d: any, i: number): string | void {}
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/timeline--chart.scss';
</style>
