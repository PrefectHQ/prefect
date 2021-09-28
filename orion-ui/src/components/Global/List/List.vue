<template>
  <ol class="list">
    <slot> </slot>
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
