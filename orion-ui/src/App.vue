<template>
  <div class="application">
    <NavBar class="nav" />
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

  display: grid;
  grid-template-areas: 'nav main';
  grid-template-columns: 62px 1fr;

  @media (max-width: 640px) {
    grid-template-areas:
      'nav'
      'main';
    grid-template-columns: unset;
    grid-template-rows: 62px 1fr;
  }

  .nav {
    grid-area: nav;
  }

  .router-view {
    grid-area: main;
    padding: 32px;
    overflow: auto;
    overscroll-behavior: contain;
    max-height: 100vh;

    @media (max-width: 640px) {
      padding: 16px;
      max-height: calc(100vh - 62px);
    }
  }
}
</style>
