import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { LoginPage } from "@/components/auth/login-page";

const loginSearchSchema = z.object({
	redirectTo: z.string().optional(),
});

export const Route = createFileRoute("/login")({
	validateSearch: zodValidator(loginSearchSchema),
	component: function LoginRouteComponent() {
		const { redirectTo } = Route.useSearch();
		return <LoginPage redirectTo={redirectTo} />;
	},
});
