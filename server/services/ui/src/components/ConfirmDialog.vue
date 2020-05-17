<script>
export default {
  props: {
    // Text displayed on the cancel button
    cancelText: {
      type: String,
      required: false,
      default: () => 'Cancel'
    },
    // Text displayed on the confirmation button
    confirmText: {
      type: String,
      required: false,
      default: () => 'Confirm'
    },
    // Props to pass to v-dialog component
    dialogProps: {
      type: Object,
      required: false,
      default: () => {}
    },
    // Disable confirmation button
    disabled: {
      type: Boolean,
      required: false,
      default: () => false
    },
    // Display loader on confirmation button
    loading: {
      type: Boolean,
      required: false,
      default: () => false
    },
    // Title on dialog card
    title: {
      type: String,
      required: false,
      default: () => ''
    },
    // Specify the type of alert
    // - "primary", the default, is typically used for save actions
    // - "error" is typically used for destructive actions
    type: {
      type: String,
      required: false,
      default: () => 'primary'
    },
    // Prop that allows users to set v-model on the dialog
    value: {
      type: Boolean,
      required: true
    }
  },
  data() {
    return {
      internalValue: this.value
    }
  },
  watch: {
    value(val) {
      // Keep the internal state of the alert on par with the value prop.
      this.internalValue = val
    }
  },
  methods: {
    emitInternalValue() {
      this.$emit('input', this.internalValue)
    },
    handleCancel() {
      this.internalValue = false
      this.$emit('cancel')
      this.emitInternalValue()
    },
    handleConfirm() {
      this.$emit('confirm')
      this.emitInternalValue()
    },
    // Propagate the internal value to the component's parent.
    // This method is what allows us to set v-model on this component.
    handleInput() {
      this.emitInternalValue()
    }
  }
}
</script>

<template>
  <v-dialog
    :value="internalValue"
    v-bind="dialogProps"
    @input="handleInput"
    @click:outside="handleCancel"
  >
    <v-card flat>
      <v-card-title class="headline word-break-normal mb-3" primary-title>
        {{ title }}
      </v-card-title>

      <v-card-text>
        <slot></slot>
      </v-card-text>

      <v-card-actions class="pb-4 px-6">
        <v-spacer></v-spacer>
        <v-btn text @click="handleCancel">
          {{ cancelText }}
        </v-btn>
        <v-btn
          :color="type"
          data-cy="confirm"
          :loading="loading"
          :disabled="disabled"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
