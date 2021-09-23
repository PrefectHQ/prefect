import { App, Plugin, ref } from 'vue'

// const FLOW_RUNS = 'host:port/flow_runs/filter'
// const FLOWs = 'host:port/flows/filter'

// export default { FLOW_RUNS, FLOWS }

// query({ ref: FLOWS, parameters: { deployment_ids: [''] } })

/*
    Name: Api / $api
    Objectives:
        - Accessible from the component interface
        - Allows polling
        - Allows refetch outside of polling period
        - Allows local polling to be stopped
        - Allows global polling to be stopped
        - Can automatically stop all data fetching when application is in the background
        - Routes with references instead of strings so components don't have to what specific routes they're hitting
            • e.g. component says `data(FLOW_RUNS)` which the plugin resolves to `host:port/flow_runs/filter`
        - Provides loading keys for data?
        - Data returned should be reactive

        this.$query.refetch()

        window.addEventListener('visibilitychange', () => {
            if(window.hidden) {
                this.$queries.global.stopPolling()
            }
        })

    Questions:
        What's the right component interface? $queries feels generic.
        Do we want to allow registering fetches in an apollo sort of way that extends the Vue instance or is inline fetching better?
          • e.g. a pattern like this:
            ```
                @Options({
                    queries: {
                        // This should be 
                        flow1: {
                            query: FLOW,
                            body() {
                                return {  } // Some filters
                            },
                            pollInterval: 10
                        }
                    }
                })
                class MyComponent {}
            ```
            or without the class component:
            ```
                export default  defineComponent({
                    queries: {
                        // This should be 
                        flow1: {
                            query: FLOW,
                            body() {
                                return {  } // Some filters
                            },
                            pollInterval: 10
                        }
                    }
                })
            ```
            or use inline like this:
            ```
                @Options({})
                class MyComponent {
                    mounted() {
                        const flows = this.$queries.register({
                            query: FLOW,
                            body: {}
                            pollInterval: 10
                        })

                        this.flows.data
                        this.flows.stopPolling()
                    },
                    setup() {
                        this.$queries.globalStopPolling()

                        const { data, stopPolling, refetch } = this.$queries.register({})
                        const flowsReactive = ref(flows)

                        return {data}
                    }
                }
            ```

            export declare interface TaskRunFilter {
  flow_run: {
    [key: string]: any
  }
}

class Queries {
  public TASKRUN: string = ''

  private query(endpoint: string, body: {[key: string]: any}) {
    {fetch(endpoint, {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
    setInterval(), stopPolling() {clearInterval(this.interval), refetch() {}}}
  }
  
  TaskRun(parameters: TaskRunFilter) {
    return this.query(parameters)
  } 
}
*/
// enum Routes {
//   count = 'count',
//   filter = 'filter'
// }

// enum Flows {
//   base = '/flows/',
//   route = keyof Routes
// }

/*
  A list where results will be returned if any of the values are included in the list
*/
declare type any_ = string[]

/*
  A list where results will be returned if values don't match any in the list
*/
declare type not_any_ = string[]

/*
  If true, returns results whose key is null
*/
declare type is_null_ = boolean

/*
  A date-time string to include results starting at or before this time
*/
declare type before_ = string

/*
  A date-time string to include results starting at or after this time
*/
declare type after_ = string

export interface FlowFilter {
  id?: {
    /*
        A list of ids
        Example: [ "abc-123", "def-456" ]
      */
    any_: any_
  }
  name?: {
    /*
        A list of names
        Example: [ "my-flow-1", "my-flow-2" ]
      */
    any_: any_
  }
  tags?: {
    /*
        Results will be returned only if their tags are a superset of the list.
    */
    all_?: any_
    /*
        If true, only include flows without tags
      */
    is_null_: is_null_
  }
  flow_runs?: FlowRunsFilter
}

export interface TaskRunsFilter {
  id?: {
    any_: any_
    not_any_: not_any_
  }
  tags?: {
    /*
        Results will be returned only if their tags are a superset of the list.
    */
    all_?: string[]
    /*
        If true, only include flow runs without tags
      */
    is_null_: is_null_
  }
  state_type?: {
    any_: any_
  }
  start_time?: {
    before_: before_
    after_: after_
  }
}

export interface FlowRunsFilter {
  id?: {
    any_: any_
    not_any_: not_any_
  }
  tags?: {
    /*
        Results will be returned only if their tags are a superset of the list.
    */
    all_?: string[]
    /*
        If true, only include flow runs without tags
      */
    is_null_: is_null_
  }
  deployment_id?: {
    any_: any_
    is_null_: is_null_
  }
  state_type?: {
    any_: any_
  }
  flow_version?: {
    any_: any_
  }
  /*
    Flow run actual starts
  */
  start_time?: {
    before_: before_
    after_: after_
  }
  /*
    Flow run scheduled starts
  */
  expected_start_time?: {
    before_: before_
    after_: after_
  }
  next_scheduled_start_time?: {
    before_: before_
    after_: after_
  }
  parent_task_run_id?: {
    any_: any_
    is_null_: is_null_
  }
  task_runs?: TaskRunsFilter
}

export type Filters = {
  flow: null
  flows: FlowFilter
  flow_runs: FlowRunsFilter
}

interface Endpoint {
  method: 'POST' | 'GET'
  url: string
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
  flow_runs: {
    method: 'POST',
    url: '/flow_runs/filter/'
  }
}

export interface QueryOptions {
  pollInterval?: number
  ignoreGlobalPolling?: boolean
}

const base_url = 'http://localhost:8000'

class Query {
  base_url: string = base_url
  body: FilterBody = {}
  endpoint: Endpoint
  pollInterval: number = 0
  value: any = ref()

  stopPolling(): void {}
  startPolling(): void {}
  refetch(): void {}

  get route(): string {
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
    { pollInterval = 0 }: QueryOptions = { pollInterval: 0 }
  ) {
    if (!endpoint)
      throw new Error('Query constructors must provide an endpoint.')
    this.endpoint = endpoint

    if (pollInterval !== 0 && pollInterval < 1000)
      throw new Error('Poll intervals cannot be less than 1000ms.')
    if (pollInterval > 0) {
      this.pollInterval = pollInterval
      this.startPolling()
    }

    this.body = body

    return this
  }
}

class Api {
  base_url: string = base_url
  queries: Query[] = []

  /*
    Makes an ad-hoc query with the given parameters
    without registering the query object
  */
  async query(endpoint: Endpoint, body: FilterBody = {}): Promise<any> {
    return await new Query(endpoint, body).fetch()
  }

  register(
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

    const query = new Query(endpoint, body, options)
    this.queries.push(query)

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
    app.config.globalProperties.$api = new Api()
  }
}

export default ApiPlugin
