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


function install(app: App) {
    for (const component in components) {
        // @ts-expect-error
        if (components[component].install) {
            // @ts-expect-error
            components[component].install(app)
        } else {
            // @ts-expect-error
            app.component(`O${component}`, components[component])
        }
    }
}

export default { install }
