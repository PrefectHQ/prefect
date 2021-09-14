<template>
  <div>
    <h1>Settings</h1>

    <section class="mt-5">
      State color mode:
      <StateColorModeSelector />
    </section>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import StateColorModeSelector from '@/components/Settings/StateColorModeSelector.vue'

@Options({
  components: { StateColorModeSelector }
})
export default class Settings extends Vue {}
</script>

<style lang="scss" scoped></style>
