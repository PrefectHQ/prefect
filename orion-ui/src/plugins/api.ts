import { App, Plugin, reactive, ref } from 'vue'

export interface FlowsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
}

export interface TaskRunsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
}

export interface FlowRunsFilter {
  limit?: limit
  offset?: offset
  flows?: FlowFilter
  flow_runs?: FlowRunFilter
  task_runs?: TaskRunFilter
}

type Filters = {
  flow: null
  flows: FlowsFilter
  flows_count: FlowsFilter
  flow_run: null
  flow_runs: FlowRunsFilter
  flow_runs_count: FlowRunsFilter
  task_run: null
  task_runs: TaskRunsFilter
  task_runs_count: TaskRunsFilter
}

type FilterBody = Filters[keyof Filters]

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
  flow_run: {
    method: 'GET',
    url: '/flow_runs/'
  },
  flow_runs: {
    method: 'POST',
    url: '/flow_runs/filter/'
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
    method: 'GET',
    url: '/task_runs/filter/'
  },
  task_runs_count: {
    method: 'GET',
    url: '/task_runs/count/'
  }
}

export interface QueryOptions {
  /**
   * This query will be sent every <pollInterval> milliseconds
   */
  pollInterval?: number
}

const base_url = 'http://localhost:8000'

export class Query {
  private interval: ReturnType<typeof setInterval> | null = null
  readonly endpoint: Endpoint
  readonly base_url: string = base_url

  body: FilterBody = {}
  id: number
  pollInterval: number = 0
  loading = ref(false)
  value: any = ref(null)

  stopPolling(): void {
    if (this.interval) clearTimeout(this.interval)
  }

  async startPolling(): Promise<void> {
    // We clear the interval to make sure we're not polling
    // more than expected
    if (this.interval) clearTimeout(this.interval)
    if (!this.pollInterval) return
    await this.refetch()
    this.interval = setTimeout(() => this.startPolling(), this.pollInterval)
  }

  async refetch(): Promise<any> {
    this.loading.value = true
    this.value.value = await this.fetch()
    this.loading.value = false
    return this.value.value
  }

  private get route(): string {
    return this.base_url + this.endpoint.url
  }

  async fetch(): Promise<any> {
    return fetch(this.route, {
      headers: { 'Content-Type': 'application/json' },
      method: this.endpoint.method,
      body: this.endpoint.method !== 'GET' ? JSON.stringify(this.body) : null
    })
      .then((res) => res)
      .then((res) => {
        if (res.status == 200) return res.json()
        throw new Error(`Response status ${res.status}: ${res.statusText}`)
      })
      .catch((err) => new Error(err))
  }

  constructor(
    endpoint: Endpoint,
    body: FilterBody = {},
    { pollInterval = 0 }: QueryOptions = { pollInterval: 0 },
    id: number
  ) {
    this.id = id

    if (!endpoint)
      throw new Error('Query constructors must provide an endpoint.')
    this.endpoint = endpoint

    if (pollInterval !== 0 && pollInterval < 1000)
      throw new Error('Poll intervals cannot be less than 1000ms.')

    this.body = body

    if (pollInterval > 0) {
      this.pollInterval = pollInterval
      this.startPolling()
    } else {
      this.refetch()
    }

    return this
  }
}

/**
  TODO: add destroy hook to remove queries from api.queries member
*/

export class Api {
  readonly base_url: string = base_url
  static queries: Map<number, Query> = new Map()

  static startPolling(): void {
    Object.values(this.queries).forEach((query) => query.startPolling())
  }

  static stopPolling(): void {
    Object.values(this.queries).forEach((query) => query.stopPolling())
  }

  /**
   * Returns an instance of the Query class and registers the query if a poll interval is specified
   */
  static query(
    endpoint: Endpoint,
    body: FilterBody = {},
    options: QueryOptions = {}
  ): Query {
    if (!endpoint)
      throw new Error('You must provide an endpoint when registering a query.')

    if (
      options.pollInterval &&
      options.pollInterval !== 0 &&
      options.pollInterval < 1000
    )
      throw new Error('Poll intervals cannot be less than 1000ms.')

    const id = this.queries.size
    const query = new Query(endpoint, body, options, id)

    if (options.pollInterval) {
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
  install(app: App, options: any = {}) {
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
