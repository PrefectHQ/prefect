import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/router-devtools'
import { QueryClient } from '@tanstack/react-query'
import { MainLayout } from '@/components/layouts/MainLayout'


interface MyRouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  staticData: {
    sideBar: false,
  },
  component: () => (
    <MainLayout>
      <Outlet />
      <TanStackRouterDevtools />
    </MainLayout>
  ),
})