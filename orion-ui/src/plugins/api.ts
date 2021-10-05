import { App, Plugin, ref, ComputedRef, watch, WatchStopHandle } from 'vue'

export interface BaseFilter {
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
  deployments?: DeploymentFilter
}

export interface LimitOffsetFilter {
  limit?: number
  offset?: number
}
export interface SortableFilter extends BaseFilter {
  // TODO: We can improve this by using keyof[Object]
  sort?: string
}

export interface HistoryFilter extends BaseFilter {
  history_start: string
  history_end: string
  history_interval_seconds: number
}

export type DeploymentsFilter = SortableFilter
export type FlowsFilter = SortableFilter
export type TaskRunsFilter = SortableFilter
export type FlowRunsFilter = SortableFilter

export type FlowRunsHistoryFilter = HistoryFilter
export type TaskRunsHistoryFilter = HistoryFilter

export interface DatabaseClearBody {
  confirm: boolean
}

export interface InterpolationBody {
  id: string
}

export interface SaveSearchBody {
  name: string
  filters: any
}

export type Filters = {
  flow: InterpolationBody
  flows: FlowsFilter
  flows_count: FlowsFilter
  flow_run: InterpolationBody
  flow_runs: FlowRunsFilter
  flow_runs_count: BaseFilter
  flow_runs_history: FlowRunsHistoryFilter
  task_run: InterpolationBody
  task_runs: TaskRunsFilter
  task_runs_count: BaseFilter
  task_runs_history: TaskRunsHistoryFilter
  deployment: InterpolationBody
  deployments: DeploymentsFilter
  deployments_count: BaseFilter
  create_flow_run: CreateFlowRunBody
  create_flow_run_from_deployment: CreateDeploymentFlowRunBody
  set_schedule_inactive: InterpolationBody
  set_schedule_active: InterpolationBody
  database_clear: DatabaseClearBody
  save_search: SaveSearchBody
  saved_searches: LimitOffsetFilter
}

export type FilterBody = Filters[keyof Filters]

export const Endpoints: { [key: string]: Endpoint } = {
  flow: {
    method: 'GET',
    url: '/flows/{id}',
    interpolate: true
  },
  flows: {
    method: 'POST',
    url: '/flows/filter'
  },
  flows_count: {
    method: 'POST',
    url: '/flows/count'
  },
  create_flow_run: {
    method: 'POST',
    url: '/flow_runs'
  },
  deployment: {
    method: 'GET',
    url: '/deployments/{id}',
    interpolate: true
  },
  deployments: {
    method: 'POST',
    url: '/deployments/filter'
  },
  deployments_count: {
    method: 'POST',
    url: '/deployments/count'
  },
  set_schedule_inactive: {
    method: 'POST',
    url: '/deployments/{id}/set_schedule_inactive',
    interpolate: true
  },
  set_schedule_active: {
    method: 'POST',
    url: '/deployments/{id}/set_schedule_active',
    interpolate: true
  },
  create_flow_run_from_deployment: {
    method: 'POST',
    url: '/deployments/{id}/create_flow_run',
    interpolate: true
  },
  flow_run: {
    method: 'GET',
    url: '/flow_runs/{id}',
    interpolate: true
  },
  flow_runs: {
    method: 'POST',
    url: '/flow_runs/filter'
  },
  flow_runs_history: {
    method: 'POST',
    url: '/flow_runs/history'
  },
  flow_runs_count: {
    method: 'POST',
    url: '/flow_runs/count'
  },
  task_run: {
    method: 'GET',
    url: '/task_runs/{id}',
    interpolate: true
  },
  task_runs: {
    method: 'POST',
    url: '/task_runs/filter'
  },
  task_runs_count: {
    method: 'POST',
    url: '/task_runs/count'
  },
  task_runs_history: {
    method: 'POST',
    url: '/task_runs/history'
  },
  save_search: {
    method: 'PUT',
    url: '/saved_searches'
  },
  saved_searches: {
    method: 'POST',
    url: '/saved_searches/filter'
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
  paused?: boolean
}

export interface QueryConfig {
  endpoint: Endpoint | undefined
  body?: FilterBody | (() => FilterBody) | ComputedRef
  options?: QueryOptions
}

const base_url = 'http://localhost:4200/api'

export class Query {
  private interval: ReturnType<typeof setInterval> | null = null
  private endpointRegex: RegExp = /{\w+}/gm
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
  async fetch(): Promise<Query> {
    this.loading.value = true
    this.error = null
    try {
      this.response.value = await this.http()
    } catch (e) {
      this.error = e
      console.error(e)
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
      } else if (cName == 'Object' || cName == 'Function') {
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
    let route = this.route
    const body = JSON.parse(JSON.stringify(this.body)) || {}

    if (this.endpoint.interpolate) {
      const keys: Array<string> = []
      route = route.replaceAll(this.endpointRegex, (match) => {
        const key = match.replace('{', '').replace('}', '')
        if (key in body) {
          keys.push(key)
          return body[key as keyof FilterBody]
        } else
          throw new Error(
            `Attempted to interpolate a url without a correct key present in the body. Expected ${key}.`
          )
      })
      keys.forEach((k, i) => {
        delete body[k]
      })
    }

    const res = await fetch(route, {
      headers: { 'Content-Type': 'application/json' },
      method: this.endpoint.method,
      body: this.endpoint.method !== 'GET' ? JSON.stringify(body) : null
    })
      .then((res) => res)
      .then((res) => {
        if (res.status == 200 || res.status == 201) return res.json()
        if (res.status == 204) return res
        console.error(this.endpoint, body)
        throw new Error(`Response status ${res.status}: ${res.statusText}`)
      })

    return res
  }

  constructor(config: QueryConfig, id: number) {
    this.id = id
    this.paused = config.options?.paused || false

    if (!config.endpoint)
      throw new Error('Query constructors must provide an endpoint.')
    this.endpoint = config.endpoint

    this.pollInterval = config?.options?.pollInterval || 0

    if (this.pollInterval !== 0 && this.pollInterval < 1000)
      throw new Error('Poll intervals cannot be less than 1000ms.')

    this.body = config.body || {}

    if (this.pollInterval > 0) {
      this.startPolling()
    } else if (!this.paused) {
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
