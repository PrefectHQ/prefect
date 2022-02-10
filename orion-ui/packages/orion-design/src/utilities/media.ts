import { media as matchMedia } from '@prefecthq/vue-compositions'
import { reactive } from 'vue'

const xs = matchMedia('(min-width: 450px)')
const sm = matchMedia('(min-width: 640px)')
const md = matchMedia('(min-width: 1024px)')
const lg = matchMedia('(min-width: 1280px)')
const xl = matchMedia('(min-width: 1440px)')

export const media = reactive({
  xs,
  sm,
  md,
  lg,
  xl,
})