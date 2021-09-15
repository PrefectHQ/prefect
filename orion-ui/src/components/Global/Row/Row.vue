<template>
  <div class="row">
    <slot />
  </div>
</template>

<script>
import { Vue } from 'vue-class-component'

class Props {}
export default class Row extends Vue.with(Props) {}
</script>

<style lang="scss" scoped>
.row {
  max-width: 100%;
  overflow-x: auto;
}
</style>
