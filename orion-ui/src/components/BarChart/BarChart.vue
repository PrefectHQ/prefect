<template>
  <div ref="container" class="chart-container">
    <svg :id="id" ref="chart" />
  </div>
</template>

<script lang="ts">
import { Options, prop, mixins } from 'vue-class-component'
import * as d3 from 'd3'
import { D3Base } from '@/components/Visualizations/D3Base'
import { createCappedBar } from '@/components/Visualizations/utils'

export interface Item {
  interval_start: Date
  interval_end: Date
  value: number
}
export type ItemCollection = Item[]

class Props {
  backgroundColor = prop<String>({ required: false, default: null })
  items = prop<ItemCollection>({ required: true })
  showAxis = prop<Boolean>({ required: false, default: false, type: Boolean })
}

const capR = 2

type SelectionType = d3.Selection<SVGGElement, unknown, HTMLElement, null>

@Options({})
export default class BarChart extends mixins(D3Base).with(Props) {
  xScale = d3.scaleTime()
  yScale = d3.scaleLinear()

  barSelection: SelectionType = null as unknown as d3.Selection<
    SVGGElement,
    unknown,
    HTMLElement,
    null
  >

  padding = {
    top: 16,
    bottom: 16,
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

  get r(): number {
    return Math.min(capR, Math.min(10, this.width / this.items.length / 2) / 2)
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
      .attr('height', '100%')

    this.barSelection = this.svg.append('g')
  }

  updateScales(): void {
    // Generate x scale
    const start = this.items?.[0]?.interval_start
    const end = this.items?.[this.items.length - 1]?.interval_end

    this.xScale.domain([new Date(start), new Date(end)]).range([0, this.width])

    // Generate y scale
    this.yScale
      .domain([0, this.maxValue])
      .range([
        this.padding.top,
        this.height -
          this.padding.bottom -
          this.padding.middle -
          this.padding.top -
          this.r * 2
      ])
  }

  updateBarPath(d: any): string | void {
    const maxWidth = this.width / this.items.length / 2
    const width = Math.min(10, maxWidth) / 2
    const xStart =
      /* @ts-ignore */
      this.xScale(new Date(d.interval_start)) + maxWidth / 2
    const height = this.yScale(d.value)
    const r = Math.min(capR, width / 2)
    const yStart = this.height - this.padding.bottom - r * 2 - height

    if (height == 0) return ''

    return createCappedBar({
      capTop: true,
      capBottom: true,
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
            .attr('id', (d: Item | any) => d.interval_start.toString())
            .append('path')
            .attr('d', this.updateBarPath)
            .attr(
              'class',
              // TODO: Figure out what the heck the overloads for D3 are supposed to be...
              /* @ts-ignore */
              (d: Item) =>
                d.value >= this.maxValue ? 'fill--primary' : 'fill--blue-20'
            ),
        (update: any) =>
          update
            .select('path')
            .attr('d', this.updateBarPath)
            .attr(
              'class',
              // TODO: Figure out what the heck the overloads for D3 are supposed to be...
              /* @ts-ignore */
              (d: Item) =>
                d.value >= this.maxValue ? 'fill--primary' : 'fill--blue-20'
            ),
        (exit: any) => exit.remove()
      )
  }

  resize(): void {
    this.svg.attr(
      'viewbox',
      `0, 0, ${this.width - this.paddingX}, ${this.height - this.paddingY}`
    )
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
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/bar--chart.scss';
</style>
