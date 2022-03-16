import { media as matchMedia } from '@prefecthq/vue-compositions'
import { reactive, Ref } from 'vue'

function tryMatchMedia(media: string): Ref<boolean> | boolean {
  try {
    return matchMedia(media)
  } catch {
    return false
  }
}

const xs = tryMatchMedia('(min-width: 450px)')
const sm = tryMatchMedia('(min-width: 640px)')
const md = tryMatchMedia('(min-width: 1024px)')
const lg = tryMatchMedia('(min-width: 1280px)')
const xl = tryMatchMedia('(min-width: 1440px)')

export const media = reactive({
  xs,
  sm,
  md,
  lg,
  xl,
})