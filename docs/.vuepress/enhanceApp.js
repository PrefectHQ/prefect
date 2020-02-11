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
    // redirect from `cloud/cloud_concepts` to `cloud/concepts`
    {
      path: '/cloud/cloud_concepts/*',
      redirect: '/cloud/concepts/*'
    },
    // redirect from `api/unreleased` to `api/latest`
    {
      path: '/api/unreleased/*',
      redirect: '/api/latest/*'
    },
    // redirect from `core/tutorials` to `core/advanced_tutorials`
    {
      path: '/core/tutorials/*',
      redirect: '/core/advanced_tutorials/*'
    },
    // redirect from `cloud/agent` to `cloud/agents`
    {
      path: '/cloud/agent/*',
      redirect: '/cloud/agents/*'
    }
  ])
}
