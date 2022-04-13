<template>
  <div class="virtual-scroller">
    <template v-for="(chunk, index) in chunks" :key="index">
      <VirtualScrollerChunk :height="itemEstimateHeight * chunk.length" v-bind="{ observerOptions }">
        <template v-for="(item, itemIndex) in chunk" :key="itemIndex">
          <slot :item="item as any" />
        </template>
      </VirtualScrollerChunk>
    </template>
    <div ref="bottom" class="virtual-scroller__bottom" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref, watch, withDefaults } from 'vue'
  import VirtualScrollerChunk from './VirtualScrollerChunk.vue'
  import { useIntersectionObserver } from '@/compositions/useIntersectionObserver'

  const props = withDefaults(defineProps<{
    // any is the correct type here
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    items: Record<string, any>[],
    itemEstimateHeight?: number,
    chunkSize?: number,
    observerOptions?: IntersectionObserverInit,
  }>(), {
    itemEstimateHeight: 50,
    chunkSize: 50,
    observerOptions: () =>({
      rootMargin: '200px',
    }),
  })

  const emit = defineEmits<{
    (event: 'bottom'): void,
  }>()

  const bottom = ref<HTMLDivElement>()
  const { observe, check } = useIntersectionObserver(intersect, props.observerOptions)

  const chunks = computed(() => {
    const chunks = []
    const source = props.items

    for (let i = 0; i < source.length; i += props.chunkSize) {
      chunks.push(source.slice(i, i + props.chunkSize))
    }

    return chunks
  })

  function intersect(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        emit('bottom')
      }
    })
  }

  watch(() => props.items, (current, previous) => {
    if (previous.length >= current.length) {
      return
    }

    check(bottom)
  })

  onMounted(() => {
    observe(bottom)
  })
</script>