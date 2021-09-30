/** A list where results will be returned only if they match all the values in the list */
type all_ = string[]

/** A list where results will be returned if any of the values are included in the list */
type any_ = string[]

/** A list where results will be returned if values don't match any in the list */
type not_any_ = string[]

/** Matches on boolean equality */
type eq_ = boolean

/** If true, returns results whose key is null */
type is_null_ = boolean

/** A date-time string to include results starting at or before this time */
type before_ = string

/** A date-time string to include results starting at or after this time */
type after_ = string

/**
 * Max: 200
 * Min: 0
 * Default: 200
 */
type limit = number

/**
 * Min: 0
 * Default: 0
 */
type offset = number

declare interface DeploymentFilter {
  id?: {
    /**
     * A list of ids
     * Example: [ "abc-123", "def-456" ]
     */
    any_: any_
  }
  name?: {
    /**
     * A list of names
     * Example: [ "my-flow-1", "my-flow-2" ]
     */
    any_: any_
  }
  tags?: {
    /**
     * Results will be returned only if their tags are a superset of the list.
     */
    all_?: any_
    /**
     * If true, only include flows without tags
     */
    is_null_: is_null_
  }
  is_schedule_active: {
    eq_: eq_
  }
}

declare interface FlowFilter {
  id?: {
    /**
     * A list of ids
     * Example: [ "abc-123", "def-456" ]
     */
    any_: any_
  }
  name?: {
    /**
     * A list of names
     * Example: [ "my-flow-1", "my-flow-2" ]
     */
    any_: any_
  }
  tags?: {
    /**
     * Results will be returned only if their tags are a superset of the list.
     */
    all_?: any_
    /**
     * If true, only include flows without tags
     */
    is_null_: is_null_
  }
}

declare interface FlowRunFilter {
  id?: {
    any_?: any_
    not_any_?: not_any_
  }
  tags?: {
    /**
     * Results will be returned only if their tags are a superset of the list.
     */
    all_?: all_
    /**
     * If true, only include flow runs without tags
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
  /**
   * Flow run actual starts
   */
  start_time?: {
    before_: before_
    after_: after_
  }
  /**
   * Flow run scheduled starts
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
}

declare interface TaskRunFilter {
  id?: {
    any_?: any_
    not_any_?: not_any_
  }
  tags?: {
    /**
     * Results will be returned only if their tags are a superset of the list.
     */
    all_?: all_
    /**
     * If true, only include flow runs without tags
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

declare interface Endpoint {
  method: 'POST' | 'GET' | 'DELETE' | 'PUT'
  url: string
}
