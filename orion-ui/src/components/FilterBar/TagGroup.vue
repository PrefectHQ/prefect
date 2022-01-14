<template>
  <div ref="container" class="filter-tag-group d-flex">
    <template v-if="overflow">
      <m-tag>
        <i class="pi pi-filter-3-line pi-xs mr--half" />
        {{ tags.length }} filters
      </m-tag>
    </template>
    <template v-else>
      <m-tag
        v-for="(tag, i) in props.tags"
        :key="i"
        class="mr--half"
        :clearable="clearable"
        @click="emit('click-tag', tag)"
        @remove="emit('remove', tag)"
      >
        <i class="pi pi-xs mr--half" :class="tag.icon" />
        {{ tag.label }}
      </m-tag>
    </template>
  </div>
</template>

<script lang="ts" setup="context">
import { onMounted, ref, computed, onBeforeUnmount } from 'vue'
import { FilterObject } from './util'
import Tag from './Tag.vue'

const props = defineProps<{
  tags: FilterObject[]
  clearable?: boolean
}>()
const emit = defineEmits(['remove', 'click-tag'])
const maxWidth = ref(0)
const container = ref()

const overflow = computed(() => {
  return props.tags.length * 250 + 250 > maxWidth.value
})

const handleResize = () => {
  maxWidth.value = container.value.parentNode.offsetWidth
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>
