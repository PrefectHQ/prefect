<template>
  <div class="home">
    <div class="hero">
      <img class="logo" src='/assets/logomark-color.svg'>
      <h1>Prefect (Preview)</h1>
      <div class="action">
        <button v-on:click.prevent="login" class="action-button data-netlify-identity-button">
          <a href="">Login</a>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
const netlifyIdentity = require("netlify-identity-widget");

export default {
  methods: {
    login () {
      netlifyIdentity.open('login')
    }
  }
}
</script>

<style lang="stylus">
.logo {
  height: 18.75em;
  margin: 6.25em 0 3em;
}
</style>
