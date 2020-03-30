export default ({ router }) => {
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
    },
        // redirect any other `/cloud` route to a `/orchestration` route
        {
          path: '/cloud',
          redirect: '/orchestration'
        },
    // redirect any other `/cloud` route to a `/orchestration` route
    {
      path: '/cloud/*',
      redirect: '/orchestration/*'
    },
    // redirect any other `/api/unreleased` route to a `/api/latest` route
    {
      path: '/api/unreleased',
      redirect: '/api/latest'
    },
    // redirect any other `/api/unreleased` route to a `/api/latest` route
    {
      path: '/api/unreleased/*',
      redirect: '/api/latest/*'
    },
  ])
}
