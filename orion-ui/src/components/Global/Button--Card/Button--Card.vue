<template>
  <button class="button-card">
    <Card
      :shadow="shadow"
      :height="height"
      :width="width"
      :miter="miter"
      style="height: inherit; width: inherit"
    >
      <div class="button-card-content pa-1">
        <slot />
      </div>
    </Card>
  </button>
</template>

<script lang="ts">
import { Vue, prop, Options } from 'vue-class-component'

class Props {
  height = prop<string>({ default: 'inherit' })
  width = prop<string>({ default: 'inherit' })
  shadow = prop<string>({ default: null })
  miter = prop<boolean>({ default: false, type: Boolean })
}

@Options({})
export default class ButtonCard extends Vue.with(Props) {}
</script>

<style lang="scss">
@use '@/styles/components/button--card.scss';
</style>
