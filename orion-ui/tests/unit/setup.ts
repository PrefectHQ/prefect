// import 'regenerator-runtime/runtime' // needed for async events
import { config } from '@vue/test-utils'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
//@ts-ignore
import MiterDesign from '@prefecthq/miter-design'

config.global.plugins.push(MiterDesign)
