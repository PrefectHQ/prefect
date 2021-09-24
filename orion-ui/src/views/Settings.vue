<template>
  <div>
    <header class="d-flex align-center justify-space-between">
      <span class="d-flex align-center">
        <i class="pi pi-settings-3-line pi-2x text--grey-40" />
        <h1 class="ml-1">Settings</h1>
      </span>
      <span class="font-weight-semibold">
        <span class="text--grey-40">Orion Version:</span>
        <span class="ml-1">{{ version }} </span>
      </span>
    </header>

    <section class="mt-1">
      <h3 class="font-weight-semibold">Color theme</h3>
      <StateColorModeSelector />
    </section>

    <!-- <section
      v-for="section in settingsSections"
      :key="section.label"
      class="mt-1"
    >
      <h3 class="font-weight-semibold">Color theme</h3>
      <StateColorModeSelector />
    </section> -->
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import StateColorModeSelector from '@/components/Settings/StateColorModeSelector.vue'
import { Api, Endpoints, Query } from '@/plugins/api'

@Options({
  components: { StateColorModeSelector }
})
export default class Settings extends Vue {
  queries: { [key: string]: Query } = {
    version: Api.query(Endpoints.version)
  }

  get version(): string {
    return this.queries.version.response
  }

  mounted() {
    fetch('http://localhost:8000/admin/version', {
      method: 'GET'
    })
  }
}
</script>

<style lang="scss" scoped></style>
