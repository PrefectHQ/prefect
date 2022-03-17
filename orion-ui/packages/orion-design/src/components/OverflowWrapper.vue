<template>
  <div class="overflow-wrapper">
    <div ref="container" class="overflow-wrapper__test">
      <slot :overflows="false" />
    </div>
    <slot :overflows="overflows" />
  </div>
</template>

<script lang="ts" setup>
  import { onMounted, ref } from 'vue'

  const overflows = ref(false)
  const container = ref<HTMLElement>()

  function setOverflows(): void {
    if (container.value) {
      overflows.value = container.value.offsetWidth < container.value.scrollWidth
    }
  }

  const observer = new ResizeObserver(() => setOverflows())

  onMounted(() => {
    if (container.value) {
      observer.observe(container.value)
    }
  })
</script>

<style lang="scss">
.overflow-wrapper {
  white-space: nowrap;
  min-width: 0;
}

.overflow-wrapper__test {
  height: 0;
  visibility: hidden;
  user-select: none;
}
</style>