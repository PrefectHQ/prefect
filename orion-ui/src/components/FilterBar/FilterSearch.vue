<template>
  <div
    class="
      search-input
      px-2
      flex-grow-1 flex-shrink-0
      d-flex
      align-center
      font--primary
      justify-space-between
    "
    @click.self="focusSearchInput"
  >
    <i class="pi pi-search-line mr-1" />
    <input
      v-model="search"
      ref="searchInput"
      class="flex-grow-1"
      placeholder="Search..."
      @focus="emitFocused"
      @input="emitInput"
      @keyup.enter="emitEnter"
    />
    <div class="d-flex align-center slot-content"> <slot /> </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, defineEmits } from 'vue'

const emit = defineEmits(['input', 'keyup.enter', 'focused'])
const searchInput = ref()
const search = ref('')

const emitInput = () => {
  emit('input', search.value)
}

const emitEnter = () => {
  emit('keyup.enter', search.value)
}

const emitFocused = () => {
  emit('focused')
}

const focusSearchInput = () => {
  searchInput.value.focus()
}
</script>

<style lang="scss" scoped>
.search-input {
  position: relative;

  input {
    border: none;
    outline: none;
    height: 100%;
  }

  .slot-content {
    z-index: 1;
  }
}
</style>
