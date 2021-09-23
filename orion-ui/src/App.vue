<template>
  <div class="application">
    <NavBar class="nav" />
    <router-view class="router-view" />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import NavBar from '@/components/ApplicationNav/NavBar.vue'
import { Endpoints, FlowsFilter } from '@/plugins/api'

@Options({
  components: { NavBar }
})
export default class App extends Vue {
  async mounted() {
    console.log(this.$api)
    const body: FlowsFilter = {
      id: { any_: ['574260d3-00e4-448e-9095-977a832241d3'] }
    }
    const flows = this.$api.register(Endpoints.flows, body)
    console.log(flows)
    const data = await flows.fetch()
    console.log(data)
  }
}
</script>

<style lang="scss">
.application {
  background-color: $grey-10;
  display: grid;
  grid-template-areas: 'nav main';
  grid-template-columns: 62px 1fr;
  height: 100vh;

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
    height: 100%;
    max-height: 100vh;
    padding: 32px;
    overflow: auto;
    overscroll-behavior: contain;

    @media (max-width: 640px) {
      padding: 16px;
      max-height: calc(100vh - 62px);
    }
  }
}
</style>
