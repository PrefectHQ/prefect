<template>
  <div ref="container" class="filter-tag-group d-flex">
    <template v-if="overflow">
      <Tag>
        <i class="pi pi-filter-3-line pi-xs mr--half" />
        {{ tags.length }} filters
      </Tag>
    </template>
    <template v-else>
      <Tag
        v-for="(tag, i) in props.tags"
        :key="i"
        class="mr--half"
        clearable
        @click="emit('click-tag', tag)"
        @remove="emit('remove', tag)"
      >
        <i class="pi pi-xs mr--half" :class="tag.icon" />
        {{ tag.label }}
      </Tag>
    </template>
  </div>
</template>

<script lang="ts" setup="context">
import {
  defineProps,
  onMounted,
  ref,
  defineEmits,
  computed,
  onBeforeUnmount
} from 'vue'
import { FilterObject } from './util'
import Tag from './Tag.vue'

const emit = defineEmits(['remove', 'click-tag'])
const maxWidth = ref(0)
const container = ref()

const overflow = computed(() => {
  return props.tags.length * 150 > maxWidth.value
})

const handleResize = () => {
  console.log(container.value)
  maxWidth.value = container.value.parentNode.offsetWidth
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})

const props = defineProps<{
  tags: FilterObject[]
}>()
</script>

<script lang="ts">
console.log(this)
</script>

<style lang="scss" scoped>
// @use '@/styles/components/global-filter--tag.scss';
</style>
