<template>
  <ListItem class="list-item--deployment" icon="pi-map-pin-line">
    <div class="list-item__title">
      <BreadCrumbs :crumbs="crumbs" tag="h2" />
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

        <span class="mr-1 text-truncate caption">
          <m-tags :tags="tags" />
        </span>
      </div>
    </div>

    <div v-if="media.sm" class="ml-auto d-flex align-middle nowrap">
      <m-toggle v-if="false" v-model="scheduleActive" />
      <m-button
        outlined
        miter
        height="36px"
        width="105px"
        class="text--grey-80"
        :disabled="creatingRun"
        @click="createRun"
      >
        Quick Run
      </m-button>
    </div>
  </ListItem>
</template>

<script lang="ts">
  /* eslint-disable */
  import { media, showPanel, DeploymentPanel, BreadCrumbs, Crumb, DeploymentsApi, FlowRunsApi, mapper, IDeploymentResponse } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/miter-design'
  import { Options, Vue, prop } from 'vue-class-component'
  import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
  import { Api, Endpoints } from '@/plugins/api'
  import { secondsToString } from '@/util/util'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'

  class Props {
    item = prop<IDeploymentResponse>({ required: true })
  }

  @Options({
    components: { ListItem, BreadCrumbs },
    watch: {
      async scheduleActive(val) {
        const endpoint = val ? 'set_schedule_active' : 'set_schedule_inactive'

        Api.query({
          endpoint: Endpoints[endpoint],
          body: { id: this.item.id },
        })
      },
    },
  })
  export default class ListItemDeployment extends Vue.with(Props) {
    search: string = ''
    scheduleActive: boolean = this.item.is_schedule_active ?? false
    creatingRun: boolean = false
    media = media
    crumbs: Crumb[] = [{ text: this.item.name, action: () => this.openDeploymentPanel() }]

    openDeploymentPanel(): void {
      showPanel(DeploymentPanel, {
        deployment: mapper.map('IDeploymentResponse', this.item, 'Deployment'),
        dashboardRoute: { name: 'Dashboard' },
        deploymentsApi: deploymentsApi as DeploymentsApi,
        flowRunsApi: flowRunsApi as FlowRunsApi,
      })
    }

    async createRun(): Promise<void> {
      this.creatingRun = true
      const res = await Api.query({
        endpoint: Endpoints.create_flow_run_from_deployment,
        body: {
          id: this.item.id,
          state: {
            type: 'SCHEDULED',
            message: 'Quick run through the Orion UI.',
          },
        },
      })

      showToast({
        type: res.error ? 'error' : 'success',
        message: res.error
          ? `Error: ${res.error}`
          : res.response.value?.name
            ? `Run created: ${res.response.value?.name}`
            : 'Run created',
        timeout: 10000,
      })
      this.creatingRun = false
    }

    get location(): string {
      return this.item.flow_data.encoding || '--'
    }

    get parameters(): Record<string, any>[] {
      return Object.entries(this.item.parameters).reduce(
        (arr: Record<string, any>[], [key, value]) => [
          ...arr,
          { name: key, value: value, type: typeof value },
        ],
        [],
      )
    }

    get schedule(): string {
      if (!this.item.schedule) {
        return '--'
      }
      if ('interval' in this.item.schedule) {
        return secondsToString(this.item.schedule.interval, false)
      }

      // TODO: add parsing for cron and RR schedules
      return '--'
    }

    get tags(): string[] {
      return this.item.tags ?? []
    }

    get filteredParameters(): Record<string, any>[] {
      return this.parameters.filter(
        (p) => p.name.includes(this.search) || p.type.includes(this.search),
      )
    }
  }
</script>

<style lang="scss" scoped>
.tag-container {
  margin-top: 6px;

  > .tag-wrapper {
    margin-top: -4px;
  }
}

.parameters-hr {
  border: 0;
  border-bottom: 1px solid;
  color: $grey-10 !important;
  width: 100%;
}

.parameter-type {
  background-color: $grey-40;
  border-radius: 4px;
}

.parameters-container {
  overflow: auto;
}
</style>
