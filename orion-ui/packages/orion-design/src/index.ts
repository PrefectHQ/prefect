export * from './components'
export * from './compositions'
export * from './mocks'
export * from './models'
export * from './maps'
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
    // @ts-expect-error any is fine here
    if (components[component].install) {
      // @ts-expect-error any is fine here
      components[component].install(app)
    } else {
      // @ts-expect-error any is fine here
      app.component(`O${component}`, components[component])
    }
  }
}

// eslint-disable-next-line import/no-default-export
export default { install }
