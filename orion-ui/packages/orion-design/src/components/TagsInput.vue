<template>
  <div class="tags-input">
    <form @submit.prevent="addTag">
      <m-input v-model="tagToAdd" placeholder="Press enter to add tags...">
        <template #prepend>
          <i class="pi pi-price-tag-line pi-sm" />
        </template>
      </m-input>
    </form>
    <div class="tags-input__tags">
      <template v-for="tag in tags" :key="tag">
        <!-- <DismissibleTag :label="tag" class="tags-input__tag" dismissible @dismiss="removeTag(tag)" /> -->
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { PropType, ref } from 'vue'
  // import DismissibleTag from '@/components/DismissibleTag.vue'

  const tagToAdd = ref<string | null>(null)

  const props = defineProps({
    tags: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  })

  const emit = defineEmits<{
    (event: 'update:tags', value: string[]): void,
  }>()

  const removeTag =(tagToRemove: string): void =>{
    emit('update:tags', [...props.tags].filter(tag => tag !== tagToRemove))
  }

  const addTag = (): void => {
    if (tagToAdd.value?.length) {
      if (props.tags.includes(tagToAdd.value)) {
        tagToAdd.value = null
        return
      }

      emit('update:tags', [...props.tags, tagToAdd.value])

      tagToAdd.value = null
    }
  }
</script>

<style lang="scss">
.tags-input__tags {
  display: flex;
  flex-wrap: wrap;
  margin: 2px;
  gap: 2px;
}
</style>