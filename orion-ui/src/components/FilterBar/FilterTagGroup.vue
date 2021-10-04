<template>
  <div ref="container" class="filter-tag-group d-flex">
    <template v-if="overflow">
      <div class="filter-tag mr-1 font--secondary caption" tabindex="0">
        <div class="px-1 py--half d-flex align-center text-capitalize">
          <i class="pi pi-filter-3-line pi-xs mr--half" />
          {{ tags.length }} filters
        </div>
      </div>
    </template>
    <template v-else>
      <FilterTag
        v-for="(tag, i) in props.tags"
        :key="i"
        :item="tag"
        class="mr--half"
        @click="emit('click-tag', tag)"
        @remove="emit('remove', tag)"
      />
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
import FilterTag from './FilterTag.vue'

const emit = defineEmits(['remove', 'click-tag'])
const maxWidth = ref(0)
const container = ref()

const overflow = computed(() => {
  return props.tags.length * 150 > maxWidth.value
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

const props = defineProps<{
  tags: FilterObject[]
}>()
</script>

<script lang="ts">
console.log(this)
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-tag.scss';
</style>
