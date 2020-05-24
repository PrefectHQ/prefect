<script>
export default {
  props: {
    crumbs: {
      type: Array,
      required: true
    }
  }
}
</script>

<template>
  <span>
    <span v-for="crumb in crumbs" :key="crumb.text">
      <RouterLink
        class="link"
        :to="crumb.route"
        :data-cy="'breadcrum-link|' + crumb.text"
      >
        {{ crumb.text }}
      </RouterLink>
      <v-icon small class="arrow-position">
        chevron_right
      </v-icon>
    </span>
  </span>
</template>

<style lang="scss" scoped>
.arrow-position {
  bottom: 1px;
  position: relative;
}
</style>
