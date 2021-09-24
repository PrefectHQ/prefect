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
      class="mt-1 setting--section my-2"
    >
      <h3 class="font-weight-semibold setting--section-title my-1">
        {{ section.key }}
      </h3>
      <section class="setting--section-content font--secondary caption">
        <div class="pa-2">
          <div v-for="_s in section.content" :key="_s.key">
            <div v-if="Array.isArray(_s.content)">
              <section
                v-for="__s in _s.content"
                :key="__s.key"
                class="setting--section-subsection"
              >
                <span>{{ __s.key }}:</span>
                <span class="ml-1">{{ __s.content }}</span>
              </section>
            </div>
            <div v-else>
              <span>{{ _s.key }}:</span>
              <span class="ml-1">{{ _s.content }}</span>
            </div>
          </div>
        </div>
      </section>
    </section>

    <section class="mt-1">
      <h3 class="font-weight-semibold">Reset database</h3>
      <div class="d-flex align-end my-1 text--error">
        <i class="pi pi-error-warning-line pi-lg" />
        <span class="ml-1">
          Resetting the database will permanently delete all data stored in
          Orion
        </span>
      </div>
      <Button
        v-if="!showResetSection"
        color="primary"
        height="36px"
        width="100px"
        class="mt-1"
        @click="showResetSection = true"
        miter
      >
        Show
      </Button>

      <section v-if="showResetSection">
        <div> Are you sure you want to permanently delete your data? </div>
        <div>
          If so, type the word <span class="text--error">Confirm</span> to
          proceed.
        </div>

        <Input
          v-model="resetDatabaseConfirmation"
          placeholder="Confirm"
          class="my-2"
          style="max-width: 400px"
        />

        <div>
          <Button
            color="primary"
            height="36px"
            :disabled="resetDatabaseConfirmation !== 'Confirm'"
            miter
            @click="resetDatabase"
          >
            Reset Database
          </Button>

          <Button
            color="secondary"
            height="36px"
            width="100px"
            class="ml-2"
            miter
            @click="showResetSection = false"
          >
            Cancel
          </Button>
        </div>
      </section>
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

  resetDatabaseConfirmation: string = ''
  showResetSection: boolean = false

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
      if (this.objectCheck(value)) {
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

  async resetDatabase(): Promise<void> {
    const { error } = await Api.query(Endpoints.universe)
    this.showConfirmationToast({
      type: error ? 'error' : 'success',
      content: error ? error : 'Database has been reset'
    })
  }

  showConfirmationToast(options: { type: string; content: any }) {
    // TODO: Add global toast notification
  }

  objectCheck(arg: any): boolean {
    return arg && typeof arg == 'object' && !Array.isArray(arg)
  }

  flatten(arr: [string, any][]): { key: string; content: any }[] {
    return arr.reduce((acc: { key: string; content: any }[], [key, value]) => {
      const obj: { key: string; content: any } = {
        key: key,
        content: undefined
      }

      if (this.objectCheck(value)) {
        obj.content = this.flatten(Object.entries(value))
      } else {
        obj.content = value
      }

      acc.push(obj)

      return acc
    }, [])
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/views/settings';
</style>
