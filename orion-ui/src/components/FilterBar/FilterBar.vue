<template>
  <div class="bar" :class="{ detached: detached }">
    I GUESS I FILTER THE PAGE

    <teleport to="#app">
      <div class="observe" ref="observe" />
    </teleport>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted } from 'vue'

const detached: Ref<boolean> = ref(false)

const handleEmit = ([entry]: IntersectionObserverEntry[]) =>
  (detached.value = !entry.isIntersecting)

const observe = ref<Element>()

let observer: IntersectionObserver

const createIntersectionObserver = (margin: string) => {
  if (observe.value) observer?.unobserve(observe.value)

  const options = {
    rootMargin: margin,
    threshold: [0.1, 1]
  }

  observer = new IntersectionObserver(handleEmit, options)
  if (observe.value) observer.observe(observe.value)
}

onMounted(() => {
  createIntersectionObserver('0px')
})

onBeforeUnmount(() => {
  if (observe.value) observer?.unobserve(observe.value)
})
</script>

<style lang="scss">
@use '@/styles/components/filter-bar.scss';
</style>
