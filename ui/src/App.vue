<template>
  <div class="application">
    <NavBar />
    <router-view class="router-view" />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import NavBar from './components/ApplicationNav/NavBar.vue'

@Options({
  components: { NavBar }
})
export default class App extends Vue {}
</script>

<style lang="scss">
.application {
  display: flex;
  align-content: stretch;

  .router-view {
    flex-grow: 1;
    flex-shrink: 0;
  }
}
</style>
