import { rand } from "@ngneat/falso";

const WORK_POOL_TYPES = [
	"kubernetes",
	"process",
	"docker",
	"vertex-ai",
	"ecs",
	"azure-container-instance",
	"cloud-run",
	"cloud-run-v2",
] as const;

export const createFakeWorkPoolType = () => {
	return rand(WORK_POOL_TYPES);
};
