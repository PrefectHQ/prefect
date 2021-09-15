<template>
  <ol class="list">
    <slot>
      <list-item>Item 1</list-item>
      <list-item>Item 2</list-item>
      <list-item>Item 3</list-item>
    </slot>
  </ol>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'

class Props {}

@Options({})
export default class List extends Vue.with(Props) {}
</script>

<style lang="scss">
@use '@/styles/components/list.scss';
</style>
