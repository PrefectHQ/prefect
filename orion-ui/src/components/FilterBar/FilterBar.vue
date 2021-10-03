<template>
  <div ref="observe" class="bar" :class="{ detached: detached }">
    I GUESS I FILTER THE PAGE
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted, nextTick, inject } from 'vue'
import { useRouter } from 'vue-router'
import Observer from '@/components/Global/IntersectionObserver/IntersectionObsever.vue'

const router = useRouter()
const detached: Ref<boolean> = ref(false)

const handleEmit = ([entry]: IntersectionObserverEntry[]) => {
  if (entry && entry.isIntersecting) {
    console.log(entry)
  }
}

const observe = ref<Element>()

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

<style lang="scss">
@use '@/styles/components/filter-bar.scss';
</style>
