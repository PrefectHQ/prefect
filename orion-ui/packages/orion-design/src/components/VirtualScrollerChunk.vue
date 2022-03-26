<template>
  <div ref="el" class="virtual-scroller-chunk" :style="styles">
    <template v-if="visible">
      <slot />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref } from 'vue'
  import { useIntersectionObserver } from '@/compositions/useIntersectionObserver'

  const props = defineProps<{
    height: number,
    observerOptions: IntersectionObserverInit,
  }>()

  const styles = computed(() => ({
    height: !visible.value ? `${height.value ?? props.height}px` : undefined,
  }))

  const el = ref<HTMLDivElement>()
  const visible = ref(false)
  const height = ref<number | null>(null)
  const { observe } = useIntersectionObserver(intersect, props.observerOptions)

  function setHeight(): void {
    setTimeout(() => {
      const rect = el.value!.getBoundingClientRect()

      height.value = rect.height
    })
  }

  function intersect(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      if (!entry.isIntersecting) {
        setHeight()
      }

      setTimeout(() => {
        visible.value = entry.isIntersecting
      })
    })
  }

  onMounted(() => {
    observe(el)
  })
</script>