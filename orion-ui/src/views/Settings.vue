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

    <section
      v-for="section in settingsSections"
      :key="section.label"
      class="mt-1"
    >
      <h3 class="font-weight-semibold">{{ section.key }}</h3>
      <code>
        {{ section.content }}
      </code>
    </section>
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
    settings: Api.query(Endpoints.settings),
    version: Api.query(Endpoints.version)
  }

  get settings(): { [key: string]: any } {
    return this.queries.settings.response
  }

  get version(): string {
    return this.queries.version.response
  }

  get settingsSections(): { [key: string]: any }[] {
    if (!this.settings) return []
    const settings: { [key: string]: any } = { ...this.settings, base: {} }
    Object.entries(settings).forEach(([key, value]) => {
      if (value && typeof value == 'object' && !Array.isArray(value)) {
        settings[key] = value
      } else {
        settings['base'][key] = value
        delete settings[key]
      }
    })
    return this.flatten(Object.entries(settings)).sort(
      (a: { key: string }, b: { key: string }) =>
        a.key.toUpperCase().localeCompare(b.key.toUpperCase())
    )
  }

  flatten(arr: [string, any][]): { key: string; content: any }[] {
    return arr.reduce((acc: { key: string; content: any }[], [key, value]) => {
      const obj: { key: string; content: any } = {
        key: key,
        content: undefined
      }

      if (value && typeof value == 'object' && !Array.isArray(value)) {
        obj.content = this.flatten(Object.entries(value))
      } else {
        obj.content = value
      }

      acc.push(obj)

      return acc
    }, [])
  }

  mounted() {
    fetch('http://localhost:8000/admin/version', {
      method: 'GET'
    })
  }
}
</script>

<style lang="scss" scoped></style>
