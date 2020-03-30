<script>
import { THEME_COLORS } from '@/plugins/vuetify'

export default {
  props: {
    color: {
      type: String,
      validator: color => THEME_COLORS[color],
      default: 'secondary'
    }
  },
  computed: {
    style() {
      return { 'background-color': THEME_COLORS[this.color] }
    }
  }
}
</script>

<template>
  <div class="emphasized-icon" :style="style">
    <slot />
  </div>
</template>

<style lang="scss" scoped>
.emphasized-icon {
  align-content: center;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  padding: 0.25rem;
}
</style>
