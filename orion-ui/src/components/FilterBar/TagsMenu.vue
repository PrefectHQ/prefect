<template>
  <Card class="tags-menu" miter shadow="sm" tabindex="0">
    <div class="menu-content pa-2">
      <h4>Apply tag filter</h4>

      <Input
        v-model="input"
        @keyup.enter="addTag"
        placeholder="Press enter to add a tag"
      />

      <div class="mt-2 tag-container">
        <FilterTag
          v-for="(tag, i) in tags"
          :key="tag"
          class="ma--half"
          :item="tag"
          @remove="removeTag(i)"
        />
      </div>
    </div>

    <template v-slot:actions>
      <hr class="hr" />

      <div class="pa-2">
        <Button class="mr-1" outlined @click="emit('close')">Cancel</Button>
        <Button color="primary" @click="apply">Apply</Button>
      </div>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { defineProps, defineEmits, reactive, ref } from 'vue'
import { useStore } from 'vuex'
import FilterTag from './FilterTag.vue'

const store = useStore()
const props = defineProps<{ object: string }>()
const emit = defineEmits(['update:modelValue', 'close'])

const input = ref('')

const icon = 'pi-price-tag-3-line'

const tags = reactive([
  ...(store.getters.globalFilter[props.object]?.tags ?? []).map((t) => {
    return { label: t, icon: icon, clearable: true }
  })
])

const addTag = () => {
  tags.push({
    label: input.value,
    icon: icon,
    clearable: true,
    value: input.value
  })
  input.value = ''
}

const removeTag = (i: number) => {
  tags.splice(i, 1)
}

const apply = () => {
  store.commit('tags', { object: props.object, tags: tags.map((t) => t.value) })
}
</script>

<style lang="scss" scoped>
.tags-menu {
  height: auto;

  .menu-content {
    min-height: 200px;
    width: 300px;

    .tag-container {
    }
  }
}

hr {
  border: 0;
  border-bottom: 1px solid;
  color: $grey-10 !important;
  width: 100%;
}
</style>
