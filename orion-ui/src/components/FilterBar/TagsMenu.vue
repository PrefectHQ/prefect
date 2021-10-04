<template>
  <Card class="run-states-menu" tabindex="0">
    <div class="menu-content pa-2">
      <h4>Apply tag filter</h4>

      <Input
        v-model="input"
        @enter="addTag"
        placeholder="Press enter to add a tag"
      />

      <div v-for="tag in tags" :key="tag"> {{ tag }}</div>
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

const store = useStore()
const props = defineProps<{ object: string }>()
const emit = defineEmits(['update:modelValue', 'close'])

const input = ref('')

const tags = reactive([
  ...(store.getters.globalFilter[props.object]?.tags ?? [])
])

const addTag = () => {
  console.log('adding tag')
  tags.push(input.value)
  input.value = ''
}

const apply = () => {
  console.log('apply')
  store.commit('tags', { object: props.object, tags: tags })
}
</script>

<style lang="scss" scoped>
.run-states-menu {
  height: auto;
}

.checkbox {
  align-items: center;
  display: flex;
  margin-left: 0 !important;
  width: min-content;

  ::v-deep(input) {
    -moz-appearance: inherit;
  }
}
</style>
