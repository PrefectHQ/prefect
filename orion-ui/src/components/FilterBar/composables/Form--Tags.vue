<template>
  <div class="container">
    <div class="font-weight-semibold d-flex align-center">
      <i class="pi text--grey-40 mr-1 pi-sm" :class="icon" />
      {{ title }}
    </div>

    <Input
      v-model="input"
      @keyup.enter="addTag"
      placeholder="Press enter to add a tag"
    />

    <div class="mt-2 tag-container">
      <Tag
        v-for="(tag, i) in tags"
        :key="tag"
        class="ma--half"
        clearable
        @remove="removeTag(i)"
      >
        <i class="pi pi-price-tag-3-line pi-xs mr--half" />
        {{ tag }}
      </Tag>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {
  defineProps,
  defineEmits,
  reactive,
  ref,
  watch,
  withDefaults
} from 'vue'
import Tag from '../Tag.vue'

const props = withDefaults(
  defineProps<{ modelValue?: string[]; title?: string; icon?: string }>(),
  { modelValue: () => [], title: 'Tags', icon: 'pi-label' }
)

const emit = defineEmits(['update:modelValue'])

const input = ref('')

const tags = reactive([...props.modelValue])

const addTag = () => {
  if (!input.value) return
  if (tags.includes(input.value)) return
  tags.push(input.value)
  input.value = ''
}

const removeTag = (i: number) => {
  tags.splice(i, 1)
}

watch(tags, () => {
  emit('update:modelValue', tags)
})
</script>

<style lang="scss" scoped>
.container {
  width: 100%;
}
</style>
