<template>
  <Select
    v-model="colorMode"
    class="my-2 mr-2"
    title="Color mode selector"
    placeholder="Color mode"
    search
  >
    <template v-slot:active>
      <div class="theme-option d-flex align-center">
        <i class="pi pi-palette-line mr-1" />
        <span>{{ colorMode }}</span>
        <div class="theme-palette ml-auto">
          <div
            v-for="color in colorMap[colorMode]"
            :key="color"
            class="palette-option"
            :style="{ 'background-color': color }"
          />
        </div>
      </div>
    </template>

    <Option v-for="mode in colorModes" :key="mode" :value="mode">
      <span class="theme-option d-flex align-center">
        <span>{{ mode }}</span>
        <div class="theme-palette ml-auto">
          <div
            v-for="color in colorMap[mode]"
            :key="color"
            class="palette-option"
            :style="{ 'background-color': color }"
          />
        </div>
      </span>
    </Option>
  </Select>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'

const states = [
  'cancelled',
  'completed',
  'failed',
  'pending',
  'running',
  'scheduled'
]

const storageKey = 'orion-color-mode'

@Options({
  components: {},
  watch: {
    colorMode(val: string) {
      localStorage.setItem(storageKey, val)

      const bodyClasses = document.body.classList
      bodyClasses.forEach((c) => {
        if (c.includes('-color-mode')) {
          document.body.classList.remove(c)
        }
      })

      document.body.classList.add(val.toLowerCase() + '-color-mode')

      this.showToast({
        type: 'success',
        content: 'Color theme saved'
      })
    }
  }
})
export default class StateColorModeSelector extends Vue {
  colorMode: string = localStorage.getItem(storageKey) || 'Default'

  colorModes: string[] = [
    'Default',
    'Achromatomaly',
    'Achromatopsia',
    'Protanomaly',
    'Protaponia',
    'Deuteranomaly',
    'Deuteranopia',
    'Tritanomaly',
    'Tritanopia'
  ]

  colorMap: { [key: string]: string[] } = {}

  showToast(options: { type: string; content: any }): void {
    this.$toast.add({ ...options, timeout: 10000 })
  }

  mounted(): void {
    // There are some plugins for rollup that make this a little easier but this seems the most straightforward
    // way if we're creating global css variables from our theme colors
    const computedStyle = window.getComputedStyle(document.documentElement)

    this.colorModes.forEach((m) => {
      const mode = m.toLowerCase()
      this.colorMap[m] = []

      states.forEach((state) => {
        const ref = `--${state}-${mode}`
        const color = computedStyle.getPropertyValue(ref)
        if (color) this.colorMap[m].push(color)
      })
    })
  }
}
</script>

<style lang="scss" scoped>
.theme-option {
  width: 100%;

  .theme-palette {
    display: inline-block;
    align-self: flex-end;

    .palette-option {
      border-radius: 50%;
      border: 1px solid #eee;
      display: inline-block;
      margin-right: 4px;
      height: 15px;
      width: 15px;
    }
  }
}
</style>
