<template>
  <button type="button" class="dismissible-tag" :class="classes" @click="dismiss">
    <span class="dismissible-tag__label">{{ label }}</span>
    <template v-if="dismissible">
      <i class="dismissible-tag__icon pi pi-xs pi-close-circle-fill" />
    </template>
  </button>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'

  const emit = defineEmits<{
    (event: 'dismiss'): void,
  }>()

  type Props = {
    label: string,
    dismissible?: boolean,
    invalid?: boolean,
  }

  const props = defineProps<Props>()

  const classes = computed(() => ({
    'dismissible-tag--dismissible': props.dismissible,
    'dismissible-tag--invalid': props.invalid,
  }))

  function dismiss(): void {
    if (props.dismissible) {
      emit('dismiss')
    }
  }
</script>

<style lang="scss" scoped>
.dismissible-tag {
  --background: var(--blue-20);
  --color: var(--grey-80);
  --icon-color: var(--primary);

  appearance: none;
  border: 0;
  background-color: var(--background);
  color: var(--color);
  border-radius: 4px;
  font-size: 14px;
  font-family: var(--font-secondary);
  padding: calc(var(--p-1) * 0.5) var(--p-1);
  display: flex;
  align-items: center;
  gap: var(--p-1);
  clip-path: var(--miter-clip-path);
  white-space: nowrap;
}

.dismissible-tag--dismissible {
  cursor: pointer;

  &:hover {
    --background: var(--primary);
    --color: #fff;
    --icon-color: #fff;
  }

  &:active {
    --background: var(--primary-hover);
  }
}

.dismissible-tag--invalid {
  --background: #fb4e4e;
}

.dismissible-tag__icon {
  color: var(--icon-color);
  transition: inherit;
  display: block;
}
</style>