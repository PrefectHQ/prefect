<template>
  <div
    class="component-container d-flex flex-column"
    style="max-height: inherit"
  >
    <div ref="container" class="scroll-container" @scroll="handleScroll">
      <div
        class="node-container"
        :style="{ height: chartHeight + 'px', width: chartWidth + 'px' }"
      >
        <div
          v-for="item in computedItems"
          :key="item.id"
          :id="`node-${item.id}`"
          class="node correct-text"
          :class="[item.state.type.toLowerCase() + '-bg']"
          :style="item.style"
          tabindex="0"
        />

        <svg :id="id" ref="chart" class="timeline-chart"></svg>

        <svg
          :id="id + '-axis'"
          ref="chart-axis"
          class="timeline-axis"
          :class="{
            top: axisPosition == 'top',
            bottom: axisPosition == 'bottom'
          }"
        ></svg>
      </div>
    </div>

    <div
      class="border-container"
      :class="{
        top: axisPosition == 'top',
        bottom: axisPosition == 'bottom'
      }"
    />

    <!-- <div
      ref="container"
      class="chart-container flex-grow-1"
      @scroll="handleScroll"
    >
     

      <svg :id="id" ref="chart" class="timeline-chart"></svg>

      <div class="node-container">
        <div
          v-for="item in computedItems"
          :key="item.id"
          :id="`node-${item.id}`"
          class="node correct-text"
          :class="[item.state.type.toLowerCase() + '-bg']"
          :style="item.style"
          tabindex="0"
        />
      </div>
    </div> -->
  </div>

  <!-- <div class="component-container">
    <IconButton
      v-if="!hideHeader"
      class="pan-button left bg--white"
      icon="pi pi-arrow-left-s-line pi-2x"
      flat
      height="36px"
      :disabled="disableLeftScrollButton"
      @click="panLeft"
    />

    <IconButton
      v-if="!hideHeader"
      class="pan-button right bg--white"
      icon="pi pi-arrow-right-s-line pi-2x"
      flat
      height="36px"
      :disabled="disableRightScrollButton"
      @click="panRight"
    />

    <div ref="container" class="chart-container" @scroll="handleScroll">
      <svg :id="id + '-axis'" ref="chart-axis" class="timeline-axis"></svg>

      <svg :id="id" ref="chart" class="timeline-chart"></svg>

      <div class="node-container">
        <div
          v-for="item in computedItems"
          :key="item.id"
          :id="`node-${item.id}`"
          class="node correct-text"
          :class="[item.state.type.toLowerCase() + '-bg']"
          :style="item.style"
          tabindex="0"
        />
      </div>
    </div>
  </div> -->
</template>

<script lang="ts">
import { TaskRun } from '@/typings/objects'
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'
import { intervals } from '@/util/util'

interface Item extends TaskRun {
  style: {
    left: string
    top: string
    width: string
  }
}

const formatMillisecond = d3.timeFormat('.%L'),
  formatSecond = d3.timeFormat('%-I:%M:%S %p'),
  formatMinute = d3.timeFormat('%-I:%M %p'),
  formatHour = d3.timeFormat('%-I %p'),
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
  axisPosition = prop<string>({ required: false, default: 'bottom' })
  backgroundColor = prop<string>({ required: false, default: null })
  items = prop<Item[]>({ required: true })
  maxEndTime = prop<string>({ required: false, default: null })
  hideHeader = prop<boolean>({
    required: false,
    default: () => false,
    type: Boolean
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
  disableLeftScrollButton: boolean = true
  disableRightScrollButton: boolean = true
  computedItems: Item[] = []
  intervalHeight: number = 24
  intervalWidth: number = 125
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  axisSvg: SelectionType = null as unknown as d3.Selection<
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

  get interval(): string {
    return Object.entries(intervals)
      .sort(([, a], [, b]) => b - a)
      .reduce(([key, val], [_key, _val]) =>
        this.totalSeconds < _val ? [_key, _val] : [key, val]
      )[0]
  }

  get numberIntervals(): number {
    return (
      Math.ceil(
        Math.max(
          this.totalSeconds / intervals[this.interval],
          this.width / this.intervalWidth
        ) / this.intervalWidth
      ) * this.intervalWidth
    )
  }

  get numberRows(): number {
    return (
      Math.ceil(
        Math.max(this.sortedItems.length, this.height / this.intervalHeight)
      ) + 3
    )
  }

  get start(): Date {
    return new Date(
      new Date(
        Math.min(
          ...this.sortedItems.map((item) => new Date(item.start_time).getTime())
        )
      ).getTime()
    )
  }

  get end(): Date {
    return new Date(
      this.maxEndTime
        ? this.maxEndTime
        : new Date(
            Math.max(
              ...this.sortedItems.map((item) =>
                item.end_time ? new Date(item.end_time).getTime() : Date.now()
              )
            )
          ).getTime()
    )
  }

  get totalSeconds(): number {
    return this.end.getTime() / 1000 - this.start.getTime() / 1000
  }

  get chartHeight(): number {
    return (
      Math.max(this.numberRows * this.intervalHeight, this.height) -
      this.paddingY -
      40
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
      .filter((item: Item) => item.state_type !== 'PENDING' && item.start_time)
  }

  xAxis = (g: any): Selection => {
    return g
      .attr('class', 'x-axis')
      .style('transform', `translate(0,${this.intervalHeight}px)`)
      .transition()
      .duration(250)
      .call(
        d3
          .axisBottom(this.xScale)
          .ticks(this.numberIntervals + 2)
          // @ts-expect-error: I haven't quite figured out the correct typing for D3 axis
          .tickFormat(formatLabel)
          .tickSizeOuter(0)
          .tickSizeInner(0)
      )
  }

  resize(): void {
    this.update()
  }

  mounted(): void {
    this.createChart()
    this.update()
    this.handleScroll()
  }

  update(): void {
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
      .range([0, this.chartWidth])
      .clamp(true) // Makes sure we don't show values outside the domain

    this.xAxisGroup.call(this.xAxis)
  }

  createChart(): void {
    this.svg = d3.select(`#${this.id}`)
    this.axisSvg = d3.select(`#${this.id}-axis`)

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
      .style('transform', 'translate(0, 36px)')

    this.xAxisGroup = this.axisSvg.append('g')
  }

  updateChart(): void {
    this.svg
      .attr('viewbox', `0, 0, ${this.chartWidth}, ${this.chartHeight}`)
      .style('width', this.chartWidth + 'px')
      .style('height', this.chartHeight + 'px')

    this.axisSvg
      .attr('viewbox', `0, 0, ${this.chartWidth}, 100`)
      .style('width', this.chartWidth + 'px')
  }

  updateNodes(): void {
    const rows: [number, number][] = []

    this.computedItems = [...this.sortedItems].map((item: Item) => {
      const start = new Date(item.start_time)
      const end = item.end_time ? new Date(item.end_time) : new Date()
      const left = this.xScale(start)
      const width = Math.max(16, this.xScale(end) - this.xScale(start))
      let row = 0

      // eslint-disable-next-line
      while (true) {
        const curr = rows[row]
        // If no row at this index, we create one instead and place this node on it
        if (curr) {
          const [, r] = curr
          // If the left edge of this node is greater than the right boundary of the
          // row, we can place it on this row
          if (left > r) {
            rows[row][1] = left + width
            break
          } else {
            row++
            continue
          }
        } else {
          rows[row] = [left, left + width]
          break
        }
      }

      return {
        ...item,
        style: {
          height: 8 + 'px',
          left: left + 'px',
          top: row * this.intervalHeight + 'px',
          transform: 'translate(0, 44px)', // 36px axis offset + height
          width: width + 'px'
        }
      }
    })
  }

  updateGrid(): void {
    // TODO: Figure out what the heck the overloads for D3 are supposed to be...
    this.gridSelection
      .selectAll('.grid-line.grid-x')
      .data(Array.from({ length: this.numberRows }))
      .join(
        (selection: any) =>
          selection
            .append('line')
            .attr('id', (d: any, i: number) => `grid-line-x-${i}`)
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

    this.gridSelection
      .selectAll('.grid-line.grid-y')
      .data(this.xScale.ticks(this.numberIntervals))
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

  handleScroll(): void {
    this.disableLeftScrollButton = this.container.scrollLeft <= 0
    this.disableRightScrollButton =
      this.container.scrollLeft >= this.container.scrollWidth
  }

  panLeft(): void {
    this.container.scroll({
      left: this.container.scrollLeft - this.width,
      behavior: 'smooth'
    })
  }

  panRight(): void {
    this.container.scroll({
      left: this.container.scrollLeft + this.width,
      behavior: 'smooth'
    })
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/timeline--chart.scss';
</style>

<style lang="scss">
@use '@prefect/miter-design/src/styles/abstracts/variables' as *;

svg.timeline-axis {
  .tick {
    font-size: 13px;
    font-family: $font--secondary;
  }

  .domain {
    opacity: 0;
  }
}
</style>
