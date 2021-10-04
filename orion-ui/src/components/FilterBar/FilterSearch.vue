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
    <div
      v-breakpoints="'xs'"
      class="d-flex align-center justify-end flex-grow-1 slot-content"
      @click.self="focusSearchInput"
    >
      <slot />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, defineEmits, onMounted, onBeforeUnmount } from 'vue'

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

const handleKeyboardEvent = (e: KeyboardEvent) => {
  if (e.key == 't') {
    focusSearchInput()
  }
}

onMounted(() => {
  window.addEventListener('keyup', handleKeyboardEvent)
})

onBeforeUnmount(() => {
  window.removeEventListener('keyup', handleKeyboardEvent)
})
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
    max-width: 50%;
    z-index: 1;
  }
}
</style>
