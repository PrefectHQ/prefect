export default {
  flow: [
    {
      id: 'a45619e1 - 64ee - 49ac - a121 - b75fbfe5f375',
      name: 'Will I Retry ? Run me to find out.',
      __typename: 'flow'
    }
  ],
  flow_run: [
    {
      id: '65bbdd76 - 0232 - 4180 - 8348 - 16f6b5bdb269',
      name: 'cream - bat',
      flow: {
        id: 'a45619e1 - 64ee - 49ac - a121 - b75fbfe5f375',
        name: 'Will I Retry ? Run me to find out.',
        __typename: 'flow'
      },
      __typename: 'flow_run'
    }
  ],
  task: [
    {
      id: '8e9bcb54 - c1ae - 42b0 - 93b1 - 14a40b3ef4cb',
      name: 'upstream',
      flow: {
        id: 'a45619e1 - 64ee - 49ac - a121 - b75fbfe5f375',
        name: 'Will I Retry ? Run me to find out.',
        __typename: 'flow'
      },
      __typename: 'task'
    }
  ],
  task_run: [
    {
      id: '70383100 - 8163 - 4c86 - 8be9 - abd5c40d0ce4',
      name: 'resourceful - mantis',
      task: {
        id: '01a02e8f - a246 - 47a1 - a62e - 5cba469abd3b',
        name: 'load',
        flow: {
          id: 'b6c41fce - 990f - 49d0 - 96c4 - 38093adc194d',
          name: 'hourly - pipeline',
          __typename: 'flow'
        },
        __typename: 'task'
      },
      __typename: 'task_run'
    }
  ]
}
