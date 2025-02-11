import { Deployment } from "@/api/deployments";

export type DeploymentSchedule = Exclude<
	Deployment["schedules"],
	undefined
>[number];
