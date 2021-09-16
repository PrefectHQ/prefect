<template>
  <li class="list--item">
    <slot />
  </li>
</template>

<script lang="ts">
import { Vue } from 'vue-class-component'

class Props {}
export default class ListItem extends Vue.with(Props) {}
</script>

<style lang="scss">
@use '@/styles/components/list--item.scss';
</style>
