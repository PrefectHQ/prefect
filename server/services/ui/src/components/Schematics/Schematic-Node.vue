<script>
import { duration } from '@/utils/moment'
import DurationSpan from '@/components/DurationSpan'
import { mapMutations, mapGetters } from 'vuex'
import StackedLineChart from '@/components/Visualizations/StackedLineChart'
import { STATE_COLORS } from '@/utils/states'

const defaultSegments = () => [
  { label: 'Pending', value: 0 },
  { label: 'Running', value: 0 },
  { label: 'Success', value: 0 },
  { label: 'Failed', value: 0 }
]

export default {
  filters: {
    duration: function(v) {
      if (!v) return ''

      const runTime = duration(v)

      if (runTime >= duration(1, 'week')) {
        return runTime.format('w[w], d[d], h[h]')
      } else if (runTime >= duration(1, 'day')) {
        return runTime.format('d d], h[h], m[m]')
      } else if (runTime >= duration(1, 'hour')) {
        return runTime.format('h[h], m[m], s[s]')
      } else if (runTime >= duration(1, 'minute')) {
        return runTime.format('m[m], s[s]')
      } else if (runTime >= duration(1, 's')) {
        return runTime.format('s[s]')
      } else if (runTime < duration(1, 'second')) {
        return '<1s'
      }
      return runTime.humanize()
    }
  },
  components: { DurationSpan, StackedLineChart },
  props: {
    // /** @typedef {import('d3').Node} Node */
    // This doesn't pass webpack compilation so disabling for now...
    // we can reinstate with TS
    k: { type: Number, required: true },
    mapped: {
      type: Array,
      required: false,
      default: () => null
    },
    nodeData: { type: null, required: true },
    disabled: { type: Boolean, required: false, default: () => false }
  },
  data() {
    return {
      scale: false,
      segments: defaultSegments()
    }
  },
  computed: {
    ...mapGetters('sideDrawer', ['currentDrawer']),
    colors() {
      return STATE_COLORS
    },
    cardStyle() {
      let top, left
      if (this.nodeData.x || this.nodeData.y) {
        left = this.nodeData.x - 250 + 'px'
        top = this.nodeData.y - 48 + 'px' // Offsets the height of the card by half
      } else {
        left =
          this.nodeData.x0 -
          (500 - (this.nodeData.x1 - this.nodeData.x0)) / 2 +
          'px'
        top =
          this.nodeData.y0 -
          (96 - (this.nodeData.y1 - this.nodeData.y0)) / 2 +
          'px' // Offsets the height of the card by half
      }
      return {
        'border-left': this.nodeData.data.state
          ? `3rem solid ${
              this.disabled
                ? this.hex2RGBA(STATE_COLORS[this.nodeData.data.state])
                : STATE_COLORS[this.nodeData.data.state]
            } !important`
          : '',
        left: left,
        top: top,
        'z-index': this.scale ? 1 : 0
      }
    },
    durationStyle() {
      let size = (1 / this.k) * 14
      size = size < 14 ? 14 : size > 32 ? 32 : size
      return {
        color: this.disabled ? '#bbb' : '',
        'font-size': `${size}px !important`,
        'line-height': `${size}px !important`
      }
    },
    isParameter() {
      return this.nodeData.data.type.split('.').pop() == 'Parameter'
    },
    titleStyle() {
      let size = (1 / this.k) * 20
      size = size < 20 ? 20 : size > 70 ? 70 : size
      return {
        color: this.disabled ? '#bbb' : '',
        'font-size': `${size}px !important`,
        'line-height': `${size + 15}px !important`
      }
    },
    subtitleStyle() {
      let size = (1 / this.k) * 20
      size = size < 20 ? 20 : size > 64 ? 64 : size
      return {
        'background-color': 'var(--v-accentOrange-base)',
        color: '#fff !important',
        'font-size': `${size}px !important`,
        'min-height': `${size + 12}px`,
        'min-width': `${size + 12}px`
      }
    }
  },
  watch: {
    mapped(val) {
      let segments = defaultSegments()
      val.forEach(task => {
        let index = segments.findIndex(s => s.label == task.state)

        if (index > -1) {
          segments[index].value++
        } else {
          segments.push({
            label: task.state,
            value: 1
          })
        }
      })
      this.segments = segments
    }
  },
  mounted() {
    if (this.mapped) {
      let segments = defaultSegments()
      this.mapped.forEach(task => {
        let index = segments.findIndex(s => s.label == task.state)

        if (index > -1) {
          segments[index].value++
        } else {
          segments.push({
            label: task.state,
            value: 1
          })
        }
      })
      this.segments = segments
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['openDrawer', 'clearDrawer']),
    wheelEvent(e) {
      if (!e) return
      e.preventDefault()

      // We can emit this later if we want to figure out
      // how best to implement zooming from the node
      // this.$emit('wheel-event', {
      //   e: e
      // })
    },
    nodeClick() {
      this.$emit('node-click', this.nodeData.data)
    },
    hex2RGBA(hex) {
      // Doesn't support 3 char hex values
      let red = hex.substr(1, 2),
        green = hex.substr(3, 2),
        blue = hex.substr(5, 4)
      let red10 = parseInt(red, 16),
        green10 = parseInt(green, 16),
        blue10 = parseInt(blue, 16)
      return `rgba(${red10}, ${green10}, ${blue10}, 0.6)`
    }
  }
}
</script>

<template>
  <v-card
    class="node pa-0"
    color="grey lighten-3"
    :style="cardStyle"
    tile
    @mouseover="scale = true"
    @mouseout="scale = false"
    @mousewheel="wheelEvent"
  >
    <v-tooltip top color="#111">
      <template v-slot:activator="{ on }">
        <v-card-text class="pa-0 h-100" v-on="on">
          <v-list-item class="h-100 " dense @click="nodeClick">
            <v-list-item-avatar v-if="isParameter" :style="subtitleStyle">
              <v-icon class="parameter-icon ma-auto">
                local_parking
              </v-icon>
            </v-list-item-avatar>

            <v-list-item-content>
              <v-list-item-title :style="titleStyle">
                {{ nodeData.data.name }}
              </v-list-item-title>
              <v-list-item-subtitle
                v-if="nodeData.data.duration || nodeData.data.start_time"
                :style="durationStyle"
              >
                Duration:
                <span v-if="nodeData.data.duration" class="font-weight-black">
                  {{ nodeData.data.duration | duration }}
                </span>
                <DurationSpan
                  v-else-if="nodeData.data.start_time"
                  :start-time="nodeData.data.start_time"
                />
              </v-list-item-subtitle>
            </v-list-item-content>

            <v-list-item-avatar class="body-2">
              <v-icon class="grey--text text--darken-2" :style="titleStyle">
                arrow_right
              </v-icon>
            </v-list-item-avatar>
          </v-list-item>
        </v-card-text>
      </template>
      <span class="accentOrange--text">
        {{ isParameter ? '[Parameter]' : '' }}
      </span>
      {{ nodeData.data.name }}

      <v-list-item-subtitle
        v-if="nodeData.data.duration || nodeData.data.start_time"
      >
        Duration:
        <span v-if="nodeData.data.duration" class="font-weight-black">
          {{ nodeData.data.duration | duration }}
        </span>
        <DurationSpan
          v-else-if="nodeData.data.start_time"
          :start-time="nodeData.data.start_time"
        />
      </v-list-item-subtitle>
    </v-tooltip>

    <div v-if="mapped" class="line-chart" :class="disabled ? 'disabled' : ''">
      <StackedLineChart :segments="segments" :colors="colors" :height="15" />
    </div>
  </v-card>
</template>

<style lang="scss" scoped>
.node {
  height: 124px;
  pointer-events: auto;
  position: absolute;
  width: 500px;

  // stylelint-disable
  .v-list-item__content,
  .v-list-item__title {
    overflow: auto !important;
  }
  // stylelint-enable
}

.h-100 {
  height: 100%;
}

.parameter-icon {
  color: inherit !important;
  font-size: inherit !important;
}

.position-relative {
  position: relative !important;
}

.line-chart {
  bottom: 0;
  height: 15px;
  left: 0;
  position: absolute !important;
  width: calc(500px - 3rem);

  &.disabled {
    opacity: 0.6;
  }
}
</style>
