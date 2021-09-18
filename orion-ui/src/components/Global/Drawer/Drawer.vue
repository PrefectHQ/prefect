<template>
  <teleport :to="target">
    <div v-if="modelValue && showOverlay" class="overlay" @click="close" />
    <transition name="slide" mode="out-in" appear>
      <aside v-if="modelValue" class="drawer pa-2">
        <h2>
          <div class="d-flex justify-start align-center">
            <Button class="mr-1" :icon="true" @click="close">
              <i class="pi pi-2x pi-arrow-left-s-line text--grey-40" />
            </Button>

            <slot v-if="$slots.title" name="title">Title</slot>
          </div>
          <hr class="title-hr" />
        </h2>

        <article class="content">
          <slot />
        </article>
      </aside>
    </transition>
  </teleport>
</template>

<script lang="ts">
import { Vue, Options, prop } from 'vue-class-component'

class Props {
  modelValue = prop<boolean>({ default: false, required: false })
  showOverlay = prop<boolean>({
    default: false,
    required: false,
    type: Boolean
  })
  target = prop<string>({ default: '.application', required: false })
}

@Options({
  emits: ['update:modelValue']
})
export default class Drawer extends Vue.with(Props) {
  close() {
    this.$emit('update:modelValue', false)
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/drawer.scss';
</style>
