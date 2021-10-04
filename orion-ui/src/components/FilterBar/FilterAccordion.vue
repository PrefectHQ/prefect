<template>
  <div class="d-flex flex-column align-self-stretch" style="width: 100%">
    <button-card
      class="expand-button"
      width="100%"
      @click="expanded = !expanded"
    >
      <div
        class="
          expand-button-content
          d-flex
          align-center align-self-stretch
          justify-space-between
        "
      >
        <i v-if="props.icon" class="pi" :class="props.icon" />
        <h3>
          {{ props.title }}
        </h3>
        <i
          class="pi pi-arrow-up-s-line expand-icon"
          :class="{ rotate: expanded }"
        />
      </div>
    </button-card>
    <!-- <div class="content-container"> -->
    <transition name="bounce" appear>
      <div v-if="expanded" class="content">
        <slot />
      </div>
    </transition>
    <!-- </div> -->
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
  //   height: auto;
  overflow: hidden;
}

.expand-icon {
  transition: all 100ms;
  transform: rotate(0);

  &.rotate {
    transform: rotate(180deg);
  }
}

.bounce-enter-active {
  animation: bounce-in 0.5s ease-out both;
}

.bounce-leave-active {
  animation: bounce-in 0.5s reverse ease-in both;
}

@keyframes bounce-in {
  0% {
    // max-height: 0;
    transform: translate(0, 0);
  }

  100% {
    // max-height: 100%;
    transform: translate(0, 100%);
  }
}
</style>
