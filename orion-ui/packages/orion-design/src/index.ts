export * from './components'
export * from './mocks'
export * from './models'
export * from './router'
export * from './services'
export * from './stores'
export * from './types'
export * from './utilities'

import { App } from 'vue'

import * as components from './components'


/* eslint-disable import/namespace */
function install(app: App): void {
  for (const component in components) {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    if (components[component].install) {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-expect-error
      components[component].install(app)
    } else {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-expect-error
      app.component(`O${component}`, components[component])
    }
  }
}

// eslint-disable-next-line import/no-default-export
export default { install }
