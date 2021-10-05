<template>
  <teleport :to="target">
    <div v-if="modelValue && showOverlay" class="overlay" @click="close" />
    <transition name="slide" mode="out-in" appear>
      <aside v-if="modelValue" class="drawer pa-2 d-flex flex-column">
        <h2>
          <div class="d-flex justify-start align-center">
            <IconButton
              class="mr-1"
              :icon="'pi-arrow-left-s-line'"
              @click="close"
            />

            <slot v-if="$slots.title" name="title">Title</slot>
          </div>
          <hr class="title-hr" />
        </h2>

        <article class="content d-flex justify-start flex-column">
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
