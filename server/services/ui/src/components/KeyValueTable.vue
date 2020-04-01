<script>
export default {
  props: {
    jsonBlob: {
      type: Object,
      required: true
    }
  },
  methods: {
    checkValue(value) {
      if (value === null) {
        return 'null'
      } else {
        return value
      }
    }
  }
}
</script>

<template>
  <table>
    <tr v-for="(value, key) in jsonBlob" :key="key">
      <!-- we remove __version__ from display because this corresponds to the
      version of Prefect Core running in Cloud, which is irrelevant and
      confusing for users to see -->
      <td v-if="key != '__version__'" class="text-left body-1">
        {{ key }}
      </td>
      <td
        v-if="key != '__version__'"
        id="value"
        class="text-right body-1 force-wrap"
      >
        {{ checkValue(value) }}
      </td>
    </tr>
  </table>
</template>

<style lang="scss" scoped>
.force-wrap {
  word-break: break-all;
  word-wrap: break-word;
}
</style>
