export const STATE_COLORS = {
  Failed: '#eb0000',
  Pending: '#b9dcff',
  Scheduled: '#ffbe1e',
  Retrying: '#fc7b09',
  Resuming: '#ffa617',
  Queued: '#fff9c2',
  Submitted: '#fff499',
  Paused: '#d4dadf',
  Running: '#27b1ff',
  Listening: '#93d8ff',
  Finished: '#003483',
  Success: '#2cbe4e',
  Cancelled: '#bdbdbd',
  Cached: '#74c367',
  TriggerFailed: '#c42800',
  Skipped: '#607583',
  TimedOut: '#dc370b',
  Mapped: '#4067a2',
  Looped: '#4c4cff'
}

export const STATE_TYPES = {
  Failed: 'Finished',
  Pending: 'Pending',
  Scheduled: 'Pending',
  Retrying: 'Pending',
  Resuming: 'Pending',
  Submitted: 'Pending',
  Paused: 'Pending',
  Queued: 'Pending',
  Running: 'Running',
  Listening: 'Running',
  Finished: 'Finished',
  Success: 'Finished',
  Cancelled: 'Finished',
  Cached: 'Finished',
  TriggerFailed: 'Finished',
  Skipped: 'Finished',
  TimedOut: 'Finished',
  Mapped: 'Finished',
  Looped: 'Finished'
}

export const STATE_NAMES = [
  'All',
  'Success',
  'Failed',
  'Scheduled',
  'Pending',
  'Running',
  'Cancelled',
  'Retrying',
  'Queued',
  'Paused',
  'Mapped',
  'Looped',
  'Skipped',
  'TriggerFailed'
]

export const STATE_PAST_TENSE = {
  Failed: 'failed',
  Pending: 'are pending',
  Scheduled: 'are scheduled',
  Retrying: 'retried',
  Resuming: 'were resumed',
  Submitted: 'are submitted',
  Paused: 'are paused',
  Queued: 'are queued',
  Running: 'are running',
  Listening: 'are listening',
  Finished: 'are finished',
  Success: 'succeeded',
  Cancelled: 'were cancelled',
  Cached: 'are cached',
  TriggerFailed: 'had failed triggers',
  Skipped: 'were skipped',
  TimedOut: 'timed out',
  Mapped: 'were mapped',
  Looped: 'were looped'
}

export default function(state) {
  return STATE_COLORS[state]
}
