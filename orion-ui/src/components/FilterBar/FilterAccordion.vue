<template>
  <div class="d-flex flex-column align-self-stretch" style="width: 100%">
    <button-card
      class="expand-button"
      width="100%"
      shadow="sm"
      @click="expanded = !expanded"
    >
      <div
        class="
          expand-button-content
          d-flex
          align-center align-self-stretch
          justify-start
        "
      >
        <i v-if="props.icon" class="pi mr-1" :class="props.icon" />
        <h3>
          {{ props.title }}
        </h3>
        <i
          class="pi pi-arrow-down-s-line expand-icon ml-auto"
          :class="{ rotate: expanded }"
        />
      </div>
    </button-card>
    <div v-if="expanded" class="content">
      <slot />
    </div>
  </div>
</template>
<script lang="ts" setup>
import { defineProps, ref } from 'vue'

const expanded = ref(false)

const props = defineProps<{ icon: string; title: string }>()
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
.expand-button {
  width: 100% !important;

  .expand-button-content {
    width: 100% !important;
  }
}

.content-container {
  max-height: min-content;
  overflow: hidden;
}

.content {
  background-color: $white;
  overflow: hidden;
}

.expand-icon {
  transition: all 100ms;
  transform: rotate(0);

  &.rotate {
    transform: rotate(180deg);
  }
}
</style>
