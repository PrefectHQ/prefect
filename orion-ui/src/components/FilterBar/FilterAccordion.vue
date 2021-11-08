<template>
  <div
    class="d-flex flex-column align-self-stretch container"
    style="width: 100%"
  >
    <ButtonCard
      class="expand-button"
      width="100%"
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
        <h4 class="font-weight-semibold">
          {{ props.title }}
        </h4>
        <i
          class="pi pi-arrow-down-s-line expand-icon ml-auto"
          :class="{ rotate: expanded }"
        />
      </div>
    </ButtonCard>
    <div v-if="expanded" class="content pa-1">
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
.container {
  filter: $drop-shadow-sm;
}
.expand-button {
  border-radius: 0 !important;
  width: 100% !important;

  ::v-deep(div) {
    border-radius: 4px 4px 0 0 !important;
  }

  .expand-button-content {
    width: 100% !important;
  }
}

.content {
  background-color: $white;
  box-shadow: $box-shadow-sm;
  border-radius: 0 0 4px 4px !important;
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
