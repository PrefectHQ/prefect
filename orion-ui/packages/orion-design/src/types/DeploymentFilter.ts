export interface DeploymentFilter {
  id?: {
    /**
     * A list of ids
     * Example: [ "abc-123", "def-456" ]
     */
    any_?: string[],
  },
  name?: {
    /**
     * A list of names
     * Example: [ "my-flow-1", "my-flow-2" ]
     */
    any_?: string[],
  },
  tags?: {
    /**
     * Results will be returned only if their tags are a superset of the list.
     */
    all_?: string[],
    /**
     * If true, only include flows without tags
     */
    is_null_?: boolean,
  },
  is_schedule_active?: {
    eq_: boolean,
  },
}