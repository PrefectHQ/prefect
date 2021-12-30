import { media } from '@prefecthq/vue-compositions'
import { reactive } from 'vue'

const xs = media('(min-width: 450px)')
const sm = media('(min-width: 640px)')
const md = media('(min-width: 1024px)')
const lg = media('(min-width: 1280px)')
const xl = media('(min-width: 1440px)')

export default reactive({
  xs,
  sm,
  md,
  lg,
  xl
})
