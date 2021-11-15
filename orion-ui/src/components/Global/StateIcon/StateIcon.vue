<template>
  <i class="pi" :class="classes" :style="styles" />
</template>

<script lang="ts">
import { Vue, prop } from 'vue-class-component'
import { State, StateColors, StateIcons } from '@/types/states'
import { StyleValue } from '@vue/runtime-dom'
import { ClassValue } from '@/types/css'
import { IconSize, getIconSizeClass } from '@/utilities/icons'
import { isState } from '@/utilities/states'

class Props {
  state = prop<State>({ required: true, validator: isState })
  size = prop<IconSize>({ default: null })
  colored = prop<boolean>({ default: false, type: Boolean })
}

export default class StateIcon extends Vue.with(Props) {
  get classes(): ClassValue {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const iconClass = StateIcons.get(this.state)!
    const sizeClass = this.size !== null ? getIconSizeClass(this.size) : ''

    return [iconClass, sizeClass]
  }

  get styles(): StyleValue {
    return {
      color: this.colored ? StateColors.get(this.state) : undefined
    }
  }
}
</script>
