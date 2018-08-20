<template>
  <div></div>
</template>

<script>

export default {
  mounted () {
    const netlifyIdentity = require("netlify-identity-widget")
    netlifyIdentity.logout()
    this.$router.push('/')
  }
}

</script>
