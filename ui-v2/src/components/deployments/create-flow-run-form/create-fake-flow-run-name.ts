import { faker } from "@faker-js/faker";

export const createFakeFlowRunName = () =>
	`${faker.word.adjective()}-${faker.animal.type()}`;
