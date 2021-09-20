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
    }
  }
})
export default class Timeline extends mixins(D3Base).with(Props) {
  computedItems: Item[] = []
  intervalHeight: number = 24
  intervalWidth: number = 125
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
    return this.totalSeconds / intervals[this.interval]
  }

  get numberRows(): number {
    return Math.max(this.items.length, this.height / this.intervalHeight)
  }

  get start(): Date {
    return new Date(this.sortedItems[0].start_time)
  }

  get end(): Date {
    return new Date(this.sortedItems[this.sortedItems.length - 1].end_time)
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
    return this.numberIntervals * this.intervalWidth - this.paddingX
  }

  get sortedItems(): Item[] {
    return this.items.sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    )
  }

  xAxis = (g: any) =>
    g
      .style('transform', `translate(0,18px)`)
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
  }

  updateScales(): void {
    // Generate x scale
    this.xScale.domain([this.start, this.end]).range([0, this.chartWidth])

    this.xAxisGroup.call(this.xAxis)

    this.computedItems = [...this.sortedItems].map((item: Item) => {
      const start = new Date(item.start_time)
      const end = new Date(item.end_time)
      return {
        ...item,
        style: {
          height: 8 + 'px',
          left: this.xScale(start) + 'px',
          top: '24px',
          transform: `translate(0, ${8}px)`,
          width: this.xScale(end) - this.xScale(start) + 'px'
        }
      }
    })
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)

    this.svg
      .attr('viewbox', `0, 0, ${this.chartWidth}, ${this.chartHeight}`)
      .style('width', this.chartWidth + 'px')
      .style('height', this.chartHeight + 'px')

    this.svg
      .append('rect')
      .attr(
        'fill',
        this.backgroundColor ? `var(--${this.backgroundColor})` : 'transparent'
      )
      .attr('rx', 4)
      .attr('width', '100%')
      .attr('height', '100%')

    this.barSelection = this.svg
      .append('g')
      .style('transform', `translate(0, 24px)`)
    this.gridSelection = this.svg
      .append('g')
      .style('transform', `translate(0, 24px)`)

    this.xAxisGroup = this.svg.append('g')
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
      text-anchor: start;
    }

    &:last-of-type {
      text-anchor: end;
    }
  }
}
</style>
