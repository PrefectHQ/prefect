<template>
  <m-popup v-model="value" position="center" class="popup-wrapper">
    <template #title>
      <slot name="title">
        <PopupTitle :color="color" :title="title" :icon="icon" />
      </slot>
    </template>
    <template #content>
      <slot />
    </template>
    <template v-if="!hideClose || !hideConfirm" #actions>
      <m-card-actions class="d-flex justify-end">
        <slot name="actions">
          <m-button
            v-if="!hideClose"
            class="mr-1"
            :color="closeColor ?? 'secondary'"
            height="36px"
            :disabled="loading"
            :miter="buttonMiter"
            @click="emit('close')"
          >
            {{ closeText ?? 'Close' }}
          </m-button>

          <m-button
            v-if="!hideConfirm"
            :color="confirmColor ?? 'primary'"
            height="36px"
            :disabled="loading"
            :miter="buttonMiter"
            @click="emit('confirm')"
          >
            {{ confirmText ?? 'Confirm' }}
          </m-button>
        </slot>
      </m-card-actions>
    </template>
  </m-popup>
</template>

<script lang="ts" setup>
  import { computed, ObjectEmitsOptions } from 'vue'
  import PopupTitle from '@/components/PopupTitle.vue'

  const props = defineProps<{
    icon?: string,
    title?: string,
    color?: 'primary' | 'error' | string,
    loading?: boolean,
    closeText?: string,
    confirmText?: string,
    hideClose?: boolean,
    hideConfirm?: boolean,
    modelValue: boolean,
    closeColor?: string
    confirmColor?: string
    buttonMiter?: boolean
  }>()

  interface IPopupEmits extends ObjectEmitsOptions {
    (event: 'update:modelValue', value: boolean): void,
    (event: 'confirm'): void,
    // If we combine these signatures, eslint loses the context of the component for some reason and every reference in the template breaks 🥲
    // eslint-disable-next-line @typescript-eslint/unified-signatures
    (event: 'close'): void,
  }

  const emit = defineEmits<IPopupEmits>()

  const value = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value),
  })
</script>

<style lang="scss">
  .popup-wrapper {
    max-width: 600px;
    width: 100%;
  }
</style>