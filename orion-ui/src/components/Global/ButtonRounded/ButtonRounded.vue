<template>
  <button class="button--rounded">
    <slot />
  </button>
</template>

<script lang="ts">
import { Vue, Options } from 'vue-class-component'

class Props {}

@Options({})
export default class ButtonCard extends Vue.with(Props) {}
</script>

<style lang="scss" scoped>
@use '@/styles/components/button--rounded.scss';
</style>
