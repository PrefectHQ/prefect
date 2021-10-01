import 'regenerator-runtime/runtime' // needed for async events
import { config } from '@vue/test-utils'
import MiterDesign from '@prefecthq/miter-design'

config.global.plugins = [MiterDesign]
