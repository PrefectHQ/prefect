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
    <transition name="expand" appear>
      <div class="content">
        <slot />
      </div>
    </transition>
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

.content {
  background-color: $white;
  height: auto;
  //   overflow: auto;
}

.expand-icon {
  transition: all 100ms;
  transform: rotate(0);

  &.rotate {
    transform: rotate(180deg);
  }
}

// .expand-leave-active {
//   animation: expand 10s reverse ease-in-out forwards;
// }

.expand-leave-active,
.expand-enter-active {
  transition: max-height 2s ease-in-out;
  //   animation: expand 10s ease-in-out forwards;
}

.expand-leave-active {
  max-height: 0 !important;
}

.expand-enter-active {
  max-height: 100% !important;
}

@keyframes expand {
  from {
    max-height: 0 !important;
  }

  to {
    max-height: 100vh !important;
  }
}
</style>
