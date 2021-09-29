<template>
  <div ref="observe" />
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const observe = ref<Element>()

const emit = defineEmits(['intersection'])

const handleEmit = ([entry]: IntersectionObserverEntry[]) => {
  if (entry && entry.isIntersecting) emit('intersection')
}

let observer: IntersectionObserver

onMounted(() => {
  const options = {
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
