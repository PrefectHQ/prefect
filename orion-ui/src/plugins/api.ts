import { App, Plugin, ref, ComputedRef, watch, WatchStopHandle } from 'vue'

export interface DeploymentsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface FlowsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface TaskRunsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface FlowRunsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface FlowRunsHistoryFilter {
  history_start: string
  history_end: string
  history_interval_seconds: number
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface DatabaseClearBody {
  confirm: boolean
}

export type Filters = {
  flow: null
  flows: FlowsFilter
  flows_count: FlowsFilter
  flow_run: null
  flow_runs: FlowRunsFilter
  flow_runs_count: FlowRunsFilter
  flow_runs_history: FlowRunsHistoryFilter
  task_run: null
  task_runs: TaskRunsFilter
  task_runs_count: TaskRunsFilter
  deployment: null
  deployments: DeploymentsFilter
  deployments_count: DeploymentsFilter
  database_clear: DatabaseClearBody
}

export type FilterBody = Filters[keyof Filters]

export const Endpoints: { [key: string]: Endpoint } = {
  flow: {
    method: 'GET',
    url: '/flows/'
  },
  flows: {
    method: 'POST',
    url: '/flows/filter/'
  },
  flows_count: {
    method: 'POST',
    url: '/flows/count/'
  },
  deployment: {
    method: 'GET',
    url: '/deployments/'
  },
  deployments: {
    method: 'POST',
    url: '/deployments/filter/'
  },
  deployments_count: {
    method: 'POST',
    url: '/deployments/count/'
  },
  flow_run: {
    method: 'GET',
    url: '/flow_runs/'
  },
  flow_runs: {
    method: 'POST',
    url: '/flow_runs/filter/'
  },
  flow_runs_history: {
    method: 'POST',
    url: '/flow_runs/history/'
  },
  flow_runs_count: {
    method: 'POST',
    url: '/flow_runs/count/'
  },
  task_run: {
    method: 'GET',
    url: '/task_runs/'
  },
  task_runs: {
    method: 'POST',
    url: '/task_runs/filter/'
  },
  task_runs_count: {
    method: 'POST',
    url: '/task_runs/count/'
  },
  settings: {
    method: 'GET',
    url: '/admin/settings'
  },
  database_clear: {
    method: 'POST',
    url: '/admin/database/clear'
  },
  version: {
    method: 'GET',
    url: '/admin/version'
  }
}

export interface QueryOptions {
  /**
   * This query will be sent every <pollInterval> milliseconds
   */
  pollInterval?: number
}

export interface QueryConfig {
  endpoint: Endpoint | undefined
  body?: FilterBody | (() => FilterBody) | ComputedRef
  options?: QueryOptions
}

const base_url = 'http://localhost:5000'

export class Query {
  private interval: ReturnType<typeof setInterval> | null = null
  readonly endpoint: Endpoint
  readonly base_url: string = base_url

  private watcher?: WatchStopHandle

  private _body(): FilterBody {
    return {}
  }
  error: string | unknown | null = null
  id: number
  pollInterval: number = 0
  loading = ref(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  response: any = ref(null)
  paused: boolean = false

  pause(): void {
    this.paused = true
  }

  resume(): void {
    this.paused = false
    this.fetch()
  }

  stopPolling(): void {
    if (this.interval) clearTimeout(this.interval)
  }

  unwatch(): void {
    if (this.watcher) this.watcher()
  }

  async startPolling(): Promise<void> {
    this.stopPolling()
    if (!this.pollInterval) return
    if (!this.paused) await this.fetch()
    this.interval = setTimeout(() => this.startPolling(), this.pollInterval)
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async fetch(): Promise<any> {
    this.loading.value = true
    this.error = null
    try {
      this.response.value = await this.http()
    } catch (e) {
      this.error = e
    } finally {
      this.loading.value = false
    }
    return this
  }

  get body(): FilterBody {
    return this._body()
  }

  set body(val: FilterBody | (() => FilterBody) | ComputedRef | null) {
    this._body = () => {
      this.unwatch()

      let _val
      if (!val) _val = {}

      const cName = val?.constructor.name
      if (cName == 'ComputedRefImpl') {
        _val = (val as ComputedRef).value

        this.watcher = watch(
          () => (val as ComputedRef).value,
          () => {
            // Check that polling is active
            if (this.pollInterval) this.startPolling()
            else if (!this.paused) this.fetch()
          }
        )
      } else if (cName == 'Object') {
        _val = val instanceof Function ? val() : val
      } else {
        _val = val
      }

      return _val
    }
  }

  private get route(): string {
    return this.base_url + this.endpoint.url
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private async http(): Promise<any> {
    return fetch(this.route, {
      headers: { 'Content-Type': 'application/json' },
      method: this.endpoint.method,
      body: this.endpoint.method !== 'GET' ? JSON.stringify(this.body) : null
    })
      .then((res) => res)
      .then((res) => {
        if (res.status == 200) return res.json()
        if (res.status == 204) return res
        throw new Error(`Response status ${res.status}: ${res.statusText}`)
      })
  }

  constructor(config: QueryConfig, id: number) {
    this.id = id

    if (!config.endpoint)
      throw new Error('Query constructors must provide an endpoint.')
    this.endpoint = config.endpoint

    this.pollInterval = config?.options?.pollInterval || 0

    if (this.pollInterval !== 0 && this.pollInterval < 1000)
      throw new Error('Poll intervals cannot be less than 1000ms.')

    this.body = config.body || {}

    if (this.pollInterval > 0) {
      this.startPolling()
    } else {
      this.fetch()
    }

    return this
  }
}

export class Api {
  readonly base_url: string = base_url
  static readonly queries: Map<number, Query> = new Map()

  static startPolling(): void {
    Object.values(this.queries).forEach((query) => query.startPolling())
  }

  static stopPolling(): void {
    Object.values(this.queries).forEach((query) => query.stopPolling())
  }

  /**
   * Returns an instance of the Query class and registers the query if a poll interval is specified
   */
  static query(config: QueryConfig): Query {
    if (!config.endpoint)
      throw new Error('You must provide an endpoint when registering a query.')

    if (
      config?.options?.pollInterval &&
      config.options.pollInterval !== 0 &&
      config.options.pollInterval < 1000
    )
      throw new Error('Poll intervals cannot be less than 1000ms.')

    const id = this.queries.size
    const query = new Query(config, id)

    if (config?.options?.pollInterval) {
      this.queries.set(id, query)
    }

    return query
  }
}

declare module '@vue/runtime-core' {
  export interface ComponentCustomProperties {
    $api: Api
  }
}

const ApiPlugin: Plugin = {
  install(app: App) {
    const api = Api
    app.config.globalProperties.$api = api
    app.provide('$api', api)

    app.mixin({
      unmounted() {
        if (this.queries && typeof this.queries == 'object') {
          Object.values(this.queries)
            .filter((query) => query instanceof Query)
            .forEach((query) => {
              ;(query as Query).stopPolling()
              Api.queries.delete((query as Query).id)
            })
        }
      }
    })
  }
}

export default ApiPlugin

// ******************************************************************************************
// Browser visibility API handler for global polling
// ******************************************************************************************

// Visibility change properties vary between browsers
let hidden: string, visibilityChange: string

declare interface DocumentExtended extends Document {
  msHidden: boolean
  webkitHidden: boolean
}

const handleVisibilityChange = async () => {
  // This weird type casting is necessary because TypeScript can be really dumb sometimes.
  if ((document as DocumentExtended)[hidden as keyof DocumentExtended]) {
    Api.stopPolling()
  } else Api.startPolling()
}

if (window) {
  if (typeof (document as DocumentExtended).msHidden !== 'undefined') {
    hidden = 'msHidden'
    visibilityChange = 'msvisibilitychange'
  } else if (
    typeof (document as DocumentExtended).webkitHidden !== 'undefined'
  ) {
    hidden = 'webkitHidden'
    visibilityChange = 'webkitvisibilitychange'
  } else {
    // Opera 12.10 and Firefox 18 and later
    hidden = 'hidden'
    visibilityChange = 'visibilitychange'
  }

  window.addEventListener(visibilityChange, handleVisibilityChange, false)
}
