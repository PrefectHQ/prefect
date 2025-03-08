import createClient from "openapi-react-query";

import { getQueryService } from "@/api/service";

export const getQueryHooks = () => {
	const client = getQueryService();
	return createClient(client);
};
