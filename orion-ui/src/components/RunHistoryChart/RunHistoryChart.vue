<template>
  <svg ref="chart" />
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import * as d3 from 'd3'

export interface Bucket {
  interval_start: Date
  interval_end: Date
  states: { [key: string]: number }
}

class Props {
  buckets = prop<Bucket[]>({ required: true })
}

@Options({})
export default class Schematic extends Vue.with(Props) {}
</script>

<style lang="scss"></style>
