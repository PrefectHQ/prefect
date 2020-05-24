<script>
import jsBeautify from 'js-beautify'
import { codemirror } from 'vue-codemirror'

export default {
  components: {
    CodeMirror: codemirror
  },
  props: {
    // If true, editor height updates based on content.
    heightAuto: {
      type: Boolean,
      default: () => false,
      required: false
    },
    value: {
      type: String,
      default: () => '',
      required: false
    }
  },
  data() {
    return {
      editorOptions: {
        autoCloseBrackets: true,
        matchBrackets: true,
        mode: 'application/json',
        smartIndent: true,
        tabSize: 2
      },

      // Line of JSON that contains a syntax error
      errorLine: null,

      // The JSON may need to be modified for formatting.
      // Store the JSON prop's value internally as data so the JSON can be modified.
      internalValue: this.value
    }
  },
  computed: {
    cmInstance() {
      return this.$refs.cmRef && this.$refs.cmRef.codemirror
    }
  },
  watch: {
    // Keep value prop in sync with value saved as data
    value() {
      this.internalValue = this.value
    }
  },
  methods: {
    formatJson() {
      this.internalValue = jsBeautify(this.internalValue, {
        indent_size: 2,
        space_in_empty_paren: true,
        preserve_newlines: false
      })
    },
    handleJsonInput(event) {
      this.removeJsonErrors()
      this.$emit('input', event)
    },
    markJsonErrors(syntaxError) {
      const errorIndex = syntaxError.message.split(' ').pop()
      const errorPosition = this.cmInstance.doc.posFromIndex(errorIndex)
      this.errorLine = errorPosition.line
      this.cmInstance.doc.addLineClass(
        this.errorLine,
        'text',
        'json-input-error-text'
      )
    },
    removeJsonErrors() {
      if (this.errorLine == null) return

      this.cmInstance.doc.removeLineClass(
        this.errorLine,
        'text',
        'json-input-error-text'
      )

      this.errorLine = null
    },
    // JSON validation is not used within this component.
    // Parent components are responsible for imperatively validating JSON using a ref to this component.
    validateJson() {
      try {
        // Treat empty or null inputs as valid
        if (!this.value || (this.value && this.value.trim() === '')) {
          return 'MissingError'
        }

        // Attempt to parse JSON and catch syntax errors
        JSON.parse(this.value)
        return true
      } catch (err) {
        if (err instanceof SyntaxError) {
          this.markJsonErrors(err)
          return 'SyntaxError'
        } else {
          throw err
        }
      }
    }
  }
}
</script>

<template>
  <div
    class="position-relative"
    :class="{ 'json-input-height-auto': heightAuto }"
  >
    <CodeMirror
      ref="cmRef"
      data-cy="code-mirror-input"
      :value="internalValue"
      class="ma-1"
      :options="editorOptions"
      :style="{
        border: '1px solid #ddd',
        'font-size': '1.3em'
      }"
      @input="handleJsonInput($event)"
    ></CodeMirror>
    <v-btn
      text
      small
      color="accent"
      class="position-absolute"
      :style="{
        bottom: '8px',
        right: '6px',
        'z-index': 3
      }"
      @click="formatJson"
    >
      Format
    </v-btn>
  </div>
</template>

<style lang="scss">
/*
  IMPORTANT: These styles must be globally scoped.

  There is CodeMirror code in <script /> that sets the .json-input-error-text class on any
  lines in the JSON editor with JSON syntax issues.

  Due to low CSS specificity, the styles in the .json-input-error-text class will not set
  if the component is locally scoped.

  For the same reason, the .json-input-error-text styles must also be marked as !important.

  To mitigate the effect of these global styles, each style will be prepended
  with json-input-, for "Run Flow Page".
*/

.json-input-height-auto {
  /* stylelint-disable selector-class-pattern */
  .CodeMirror {
    height: auto;
    min-height: 108px;
  }
  /* stylelint-enable selector-class-pattern */
}

.json-input-error-text {
  text-decoration: #ff5252 wavy underline !important;
}
</style>
