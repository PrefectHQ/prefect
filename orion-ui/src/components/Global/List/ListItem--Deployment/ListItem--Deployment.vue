<template>
  <list-item class="list-item--deployment d-flex align-start justify-start">
    <i class="item--icon pi pi-map-pin-line text--grey-40 align-self-start" />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ item.name }}
      </h2>

      <div
        class="
          tag-container
          font-weight-semibold
          nowrap
          caption
          d-flex
          align-bottom
        "
      >
        <span
          v-if="schedule"
          class="mr-1 caption text-truncate d-flex align-center"
        >
          <i class="pi pi-calendar-line pi-sm text--grey-20" />
          <span
            class="text--grey-80 ml--half font--primary"
            style="min-width: 0px"
          >
            {{ schedule !== '--' ? 'Every' : '' }} {{ schedule }}
          </span>
        </span>

        <span class="mr-1 caption text-truncate d-flex align-center">
          <i class="pi pi-global-line pi-sm text--grey-20" />
          <span
            class="text--grey-80 ml--half font--primary"
            style="min-width: 0px"
          >
            {{ location }}
          </span>
        </span>

        <span class="mr-1 caption text-truncate d-flex align-center">
          <Tag
            v-for="tag in tags"
            :key="tag"
            color="secondary-pressed"
            class="font--primary mr-1"
            icon="pi-label"
            flat
          >
            {{ tag }}
          </Tag>
        </span>
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto d-flex align-middle nowrap">
      <Toggle v-if="false" v-model="scheduleActive" />

      <Button
        outlined
        height="36px"
        width="160px"
        class="mr-1 text--grey-80"
        @click="parametersDrawerActive = true"
      >
        View Parameters
      </Button>
      <Button
        outlined
        miter
        height="36px"
        width="105px"
        class="text--grey-80"
        :disabled="creatingRun"
        @click="createRun"
      >
        Quick Run
      </Button>
    </div>
  </list-item>

  <drawer v-model="parametersDrawerActive" show-overlay>
    <template #title>{{ item.name }}</template>
    <h3 class="font-weight-bold">Parameters</h3>
    <div>These are the inputs that are passed to runs of this Deployment.</div>

    <hr class="mt-2 parameters-hr align-self-stretch" />

    <Input v-model="search" placeholder="Search...">
      <template #prepend>
        <i class="pi pi-search-line"></i>
      </template>
    </Input>

    <div class="mt-2 font--secondary">
      {{ filteredParameters.length }} result{{
        filteredParameters.length !== 1 ? 's' : ''
      }}
    </div>

    <hr class="mt-2 parameters-hr" />

    <div class="parameters-container pr-2 align-self-stretch">
      <div v-for="(parameter, i) in filteredParameters" :key="i">
        <div class="d-flex align-center justify-space-between">
          <div class="caption font-weight-bold font--secondary">
            {{ parameter.name }}
          </div>
          <span
            class="
              parameter-type
              font--secondary
              caption-small
              px-1
              text--white
            "
          >
            {{ parameter.type }}
          </span>
        </div>

        <p class="font--secondary caption">
          {{ parameter.value }}
        </p>

        <hr
          v-if="i !== filteredParameters.length - 1"
          class="mb-2 parameters-hr"
        />
      </div>
    </div>
  </drawer>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { secondsToString } from '@/util/util'
import { Deployment, IntervalSchedule, CronSchedule } from '@/typings/objects'
import { Api, Endpoints } from '@/plugins/api'

class Props {
  item = prop<Deployment>({ required: true })
}

@Options({
  watch: {
    parametersDrawerActive() {
      this.search = ''
    },
    async scheduleActive(val) {
      const endpoint = val ? 'set_schedule_active' : 'set_schedule_inactive'

      Api.query({
        endpoint: Endpoints[endpoint],
        body: { id: this.item.id }
      })
    }
  }
})
export default class ListItemDeployment extends Vue.with(Props) {
  parametersDrawerActive: boolean = false
  search: string = ''
  scheduleActive: boolean = this.item.is_schedule_active
  creatingRun: boolean = false

  async createRun(): Promise<void> {
    this.creatingRun = true
    const res = await Api.query({
      endpoint: Endpoints.create_flow_run,
      body: {
        deployment_id: this.item.id,
        flow_id: this.item.flow_id,
        name: 'testingggggggg a longgggg name with lots of gggggggs and yyyyyyyyys',
        state: {
          type: 'SCHEDULED',
          message: 'Quick run through the Orion UI.'
        }
      }
    })
    console.log(res)
    this.$toast.add({
      type: res.error ? 'error' : 'success',
      content: res.error
        ? `Error: ${res.error}`
        : `Run created: ${res.response.value?.name}`,
      timeout: 10000
    })
    this.creatingRun = false
  }

  get location(): string {
    return this.item.flow_data.blob || '--'
  }

  get parameters(): { [key: string]: any }[] {
    return Object.entries(this.item.parameters).reduce(
      (arr: { [key: string]: any }[], [key, value]) => [
        ...arr,
        { name: key, value: value, type: typeof value }
      ],
      []
    )
  }

  get schedule(): string {
    if (!this.item.schedule) return '--'
    if ('interval' in this.item.schedule)
      return secondsToString(this.item.schedule.interval, false)

    // TODO: add parsing for cron and RR schedules
    return '--'
  }

  get tags(): string[] {
    return this.item.tags
  }

  get filteredParameters(): { [key: string]: any }[] {
    return this.parameters.filter(
      (p) => p.name.includes(this.search) || p.type.includes(this.search)
    )
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--deployment.scss';
</style>
