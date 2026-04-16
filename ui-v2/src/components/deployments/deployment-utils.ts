import type { Deployment } from "@/api/deployments";

/**
 * A deployment is considered deprecated when it has no entrypoint. These are
 * deployments created prior to the Prefect 2 GA release (pre-entrypoint era)
 * and should have a reduced surface on the detail page.
 */
export const isDeploymentDeprecated = (deployment: Deployment): boolean =>
	deployment.entrypoint === "" || deployment.entrypoint === null;
