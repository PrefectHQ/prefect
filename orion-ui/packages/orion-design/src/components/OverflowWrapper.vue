<template>
  <div class="overflow-wrapper">
    <div ref="container" class="overflow-wrapper__test">
      <slot :overflown="false" />
    </div>
    <slot :overflown="overflown" />
  </div>
</template>

<script lang="ts" setup>
  import { onMounted, ref } from 'vue'

  const overflown = ref(false)
  const container = ref<HTMLElement>()

  const observer = new ResizeObserver(([entry]) => {
    const target = entry.target as HTMLElement

    overflown.value = target.offsetWidth < target.scrollWidth
  })

  onMounted(() => {
    if (container.value) {
      observer.observe(container.value)
    }
  })
</script>

<style lang="scss">
.overflow-wrapper {
  white-space: nowrap;
  overflow: auto;
}

.overflow-wrapper__test {
  height: 0;
  visibility: hidden;
  user-select: none;
  overflow: hidden;
}
</style>