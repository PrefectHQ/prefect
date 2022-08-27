export const pages = {
  root: () => '/' as const,
  flowRuns: () => '/runs' as const,
  flowRun: (id: string) => `/flow-run/${id}` as const,
  flowRunRadar: (id: string) => `/flow-run/${id}/radar` as const,
  flows: () => '/flows' as const,
  flow: (id: string) => `/flow/${id}` as const,
  deployments: () => '/deployments' as const,
  deployment: (id: string) => `/deployment/${id}` as const,
  deploymentEdit: (id: string) => `/deployment/${id}/edit` as const,
  workQueues: () => '/work-queues' as const,
  workQueue: (id: string) => `/work-queue/${id}` as const,
  workQueuesCreate: () => '/work-queues/new' as const,
  workQueueEdit: (id: string) => `/work-queue/${id}` as const,
  blocks: () => '/blocks' as const,
  blocksCatalog: () => '/blocks/catalog' as const,
  blocksCatalogView: (blockTypeSlug: string) => `/blocks/catalog/${blockTypeSlug}` as const,
  blocksCatalogCreate: (blockTypeSlug: string) => `/blocks/catalog/${blockTypeSlug}/create` as const,
  block: (id: string) => `/block/${id}` as const,
  blockEdit: (id: string) => `/block/${id}/edit` as const,
  notifications: () => '/notifications' as const,
  notificationsCreate: () => '/notifications/new' as const,
  notificationEdit: (id: string) => `/notifications/${id}` as const,
  settings: () => '/settings' as const,
}

export type Pages = typeof pages
export type Page = ReturnType<Pages[keyof Pages]>