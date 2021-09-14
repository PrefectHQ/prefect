import 'regenerator-runtime/runtime' // needed for async events
import { config } from '@vue/test-utils'
import MiterDesign from '@prefect/miter-design'

config.global.plugins = [MiterDesign]
