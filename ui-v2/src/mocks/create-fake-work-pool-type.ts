import { faker } from "@faker-js/faker";

const WORK_POOL_TYPES = [
	"kubernetes",
	"process",
	"docker",
	"google-vertex-ai",
	"ecs",
	"azure-container-instance",
	"cloud-run",
	"cloud-run-v2",
] as const;

export const createFakeWorkPoolType = () => {
	return faker.helpers.arrayElement(WORK_POOL_TYPES);
};
