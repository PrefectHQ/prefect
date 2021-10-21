// import vClickOutside from 'v-click-outside'

export default ({ Vue, router }) => {
  // Vue.use(vClickOutside)
  if (typeof window !== 'undefined') {
    if (window && window.location && window.location.hash) {
      document.onreadystatechange = () => {
        if (document.readyState == 'complete') {
          scrollToHash(window.location, Vue)

          document.onreadystatechange = null
        }
      }
    }
  }

  router.options.scrollBehavior = (to, from, savedPosition) => {
    if (savedPosition) {
      if (typeof window !== 'undefined') {
        return (
          window &&
          window.scrollTo({
            top: savedPosition.y,
            behavior: 'smooth'
          })
        )
      }
    } else if (to.hash) {
      scrollToHash(to, Vue)
      return false
    } else {
      if (typeof window !== 'undefined') {
        return (
          window &&
          window.scrollTo({
            top: 0,
            behavior: 'smooth'
          })
        )
      }
    }
    return false
  }

  router.addRoutes([
    // redirect from `guide/core_concepts` to `core/concepts`
    {
      path: '/guide/core_concepts/*',
      redirect: '/core/concepts/*'
    },
    // redirect any other `/guide` route to a `/core` route
    {
      path: '/guide/*',
      redirect: '/core/*'
    }
  ])
}

function scrollToHash(to, Vue) {
  if (Vue.$vuepress.$get('disableScrollBehavior')) {
    return false
  }

  const targetElement = document.querySelector(to.hash)

  if (targetElement && typeof window !== 'undefined') {
    return (
      window &&
      window.scrollTo({
        top: getElementPosition(targetElement).y,
        behavior: 'smooth'
      })
    )
  }
  return false
}

function getElementPosition(el) {
  const docEl = document.documentElement
  const docRect = docEl.getBoundingClientRect()
  const elRect = el.getBoundingClientRect()
  return {
    x: elRect.left - docRect.left,
    y: elRect.top - docRect.top
  }
}
