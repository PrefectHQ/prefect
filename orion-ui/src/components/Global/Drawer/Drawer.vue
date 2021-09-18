<template>
  <teleport :to="target">
    <aside class="drawer">
      <slot />
    </aside>
  </teleport>
</template>

<script lang="ts">
import { Vue, Options, prop } from 'vue-class-component'

class Props {
  target = prop<string>({ default: '#app', required: false })
}

@Options({})
export default class Drawer extends Vue.with(Props) {}
</script>

<style lang="scss" scoped>
@use '@/styles/components/drawer.scss';
</style>
