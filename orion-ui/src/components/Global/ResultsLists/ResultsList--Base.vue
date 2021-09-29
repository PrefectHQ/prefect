<template>
  <div ref="container" class="container" :style="{ height: height + 'px' }">
    <slot />
    <div ref="observe" />
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'

const container = ref<HTMLElement>()
const observe = ref<Element>()

const height = ref(0)

const emit = defineEmits(['load-more'])

const handleEmit = (entries: IntersectionObserverEntry[]) => {
  if (entries.length > 0) emit('load-more')
}

let observer: IntersectionObserver

onMounted(() => {
  height.value = container.value!.parentElement!.clientHeight

  const options = {
    root: container.value,
    rootMargin: '0px',
    threshold: 0.1
  }

  observer = new IntersectionObserver(handleEmit, options)
  observer.observe(observe.value!)
})

onBeforeUnmount(() => {
  observer.unobserve(observe.value!)
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/results-list.scss';
</style>
