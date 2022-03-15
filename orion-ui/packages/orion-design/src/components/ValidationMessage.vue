<template>
  <div v-if="errors.length" class="validation-message">
    <i class="pi pi-error-warning-line pi-lg" />
    <ul class="validation-message__list" :class="{ 'validation-message__list--single': errors.length === 1 }">
      <template v-for="(error, index) in errors" :key="index">
        <li class="validation-message__list-item">
          {{ error }}
        </li>
      </template>
      <template v-if="suggest">
        <li class="validation-message__list-item--suggestion">
          <a class="validation-message__suggestion-link" @click.prevent="applySuggestion">
            <template v-if="typeof suggest === 'string'">
              use "{{ suggest }}"
            </template>
            <template v-else>
              {{ suggest.text }}
            </template>
          </a>
        </li>
      </template>
    </ul>
  </div>
</template>

<script lang="ts" setup>
  const props = defineProps<{
    errors: string[],
    suggest?: string | { text: string, value?: string },
  }>()

  const emits = defineEmits<{
    (event: 'apply', value: string | undefined): void,
  }>()

  function applySuggestion(): void {
    emits('apply', typeof props.suggest === 'string'
      ? props.suggest
      : props.suggest?.value)
  }
</script>

<style lang="scss">
.validation-message {
  display: flex;
  align-items: center;
  min-height: 48px;
  column-gap: var(--m-1);
  color: var(--error);
}

.validation-message__list {
  padding-left: var(--p-2);
  margin: 0;
}

.validation-message__list-item--suggestion {
  list-style-type: none;
  margin-left: calc(var(--p-2) * -1)
}

.validation-message__list--single {
  list-style-type: none;
  padding-left: 0;

  .validation-message__list-item--suggestion {
    margin-left: 0;
  }
}

.validation-message__suggestion-link {
  color: var(--error) !important;
  font-weight: bold;
}
</style>