<template>
  <div class="application">
    <NavBar />
    <router-view class="router-view" />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import NavBar from '@/components/ApplicationNav/NavBar.vue'

@Options({
  components: { NavBar }
})
export default class App extends Vue {}
</script>

<style lang="scss">
.application {
  background-color: $grey-10;

  display: flex;
  align-content: stretch;

  @media (max-width: 640px) {
    flex-direction: column;
  }

  .router-view {
    flex-grow: 1;
    flex-shrink: 0;
    padding: 32px;

    @media (max-width: 640px) {
      padding: 16px;
    }
  }
}
</style>
