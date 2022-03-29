<template>
  <div>
    <header class="d-flex align-center justify-space-between mt-2">
      <span class="d-flex align-center">
        <i class="pi pi-settings-3-line pi-2x text--grey-40" />
        <h1 class="ml-1">Settings</h1>
      </span>
      <span class="font-weight-semibold">
        <span class="text--grey-40">Orion Version:</span>
        <span class="ml-1">{{ version }} </span>
      </span>
    </header>

    <section class="mt-4">
      <h3 class="font-weight-semibold my-1">
        Color theme
      </h3>
      <ColorSchemeSelect />
    </section>

    <section
      v-for="section in settingsSections"
      :key="section.label"
      class="mt-4 setting--section my-2"
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

    <section class="my-4">
      <h3 class="font-weight-semibold">
        Reset database
      </h3>
      <div class="d-flex align-end my-1 text--error">
        <i class="pi pi-error-warning-line pi-lg" />
        <span class="ml-1">
          Resetting the database will permanently delete all data stored in
          Orion
        </span>
      </div>
      <m-button
        v-if="!showResetSection"
        color="delete"
        height="36px"
        width="100px"
        class="mt-1"
        miter
        @click="showResetSection = true"
      >
        Reset
      </m-button>

      <section v-if="showResetSection">
        <div> Are you sure you want to permanently delete your data? </div>
        <div>
          If so, type the word <span class="text--error">CONFIRM</span> to
          proceed.
        </div>

        <m-input
          v-model="resetDatabaseConfirmation"
          placeholder="CONFIRM"
          class="my-2"
          style="max-width: 400px"
        />

        <div>
          <m-button
            color="delete"
            height="36px"
            :disabled="resetDatabaseConfirmation !== 'CONFIRM'"
            miter
            @click="resetDatabase"
          >
            Reset Database
          </m-button>

          <m-button
            color="secondary"
            height="36px"
            width="100px"
            class="ml-2"
            miter
            @click="showResetSection = false"
          >
            Cancel
          </m-button>
        </div>
      </section>
    </section>
  </div>
</template>

<script lang="ts">
  import { ColorSchemeSelect } from '@prefecthq/orion-design'
  import { Options, Vue } from 'vue-class-component'
  import { Api, Endpoints, Query } from '@/plugins/api'

  @Options({
    components: { ColorSchemeSelect },
  })
  export default class Settings extends Vue {
    queries: Record<string, Query> = {
      settings: Api.query({ endpoint: Endpoints.settings }),
      version: Api.query({ endpoint: Endpoints.version }),
    }

    resetDatabaseConfirmation: string = ''
    showResetSection: boolean = false

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get settings(): Record<string, any> {
      return this.queries.settings.response
    }

    get version(): string {
      return this.queries.version.response
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get settingsSections(): Record<string, any>[] {
      if (!this.settings) {
        return []
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const settings: Record<string, any> = { ...this.settings, base: {} }
      // Go one level down on orion section
      Object.entries(settings).forEach(([key, value]) => {
        if (this.objectCheck(value)) {
          settings[key] = value
        } else {
          settings.base[key] = value
          delete settings[key]
        }
      })
      return this.flatten(Object.entries(settings)).sort(
        (a: { key: string }, b: { key: string }) => a.key.toUpperCase().localeCompare(b.key.toUpperCase()),
      )
    }

    async resetDatabase(): Promise<void> {
      const query = await Api.query({
        endpoint: Endpoints.database_clear,
        body: { confirm: true },
      }).fetch()
      this.showToast({
        type: query.error ? 'error' : 'success',
        message: query.error ? query.error : 'Database reset',
      })
    }

    showToast(options: { type: string, message: string }): void {
      this.$toast({ ...options, timeout: 5000 })
    }

    // eslint-disable-next-line @typescript-eslint/explicit-module-boundary-types, @typescript-eslint/no-explicit-any
    objectCheck(arg: any): boolean {
      return arg && typeof arg == 'object' && !Array.isArray(arg)
    }

    /* eslint-disable @typescript-eslint/no-explicit-any */
    flatten(arr: [string, any][]): { key: string, content: any }[] {
      return arr.reduce((acc: { key: string, content: any }[], [key, value]) => {
        const obj: { key: string, content: any } = {
          key: key,
          content: undefined,
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
  /* eslint-enable @typescript-eslint/no-explicit-any */
  }
</script>

<style lang="scss" scoped>
@use '@/styles/views/settings';
</style>
