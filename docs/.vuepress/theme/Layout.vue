<template>
  <div>
      <Layout v-if="loggedIn"></Layout>
      <Login v-else/>
  </div>
</template>

<script>

import Layout from '@default-theme/Layout.vue'

export default {
  components: {
    Layout
  },
  data() {
    return {
      loggedIn: false,
    }
  },
  methods:  {
    logOut () {
        this.$data.loggedIn = false
      },
    logIn (user) {
      const netlifyIdentity = require("netlify-identity-widget");
      if (!user) {
        this.logOut();
      } else {
        this.$data.loggedIn = true
      }
      netlifyIdentity.close()
    },
  },

  mounted() {
    const netlifyIdentity = require("netlify-identity-widget");

    netlifyIdentity.init()
    netlifyIdentity.on('init', this.logIn )
    netlifyIdentity.on('login', this.logIn )
    netlifyIdentity.on('logout', this.logOut)

    const user = netlifyIdentity.currentUser()
    if (user) {
      this.logIn(user)
    }

    this.$router.beforeEach((to, from, next) => {
      const user = netlifyIdentity.currentUser()
      if (user) {
        this.logIn(user)
      } else {
        this.logOut(user)
      }
      next()
    })
  }
}
</script>
