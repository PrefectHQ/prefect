import { useNavigate } from "@tanstack/react-router";
import { type FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PrefectLogo } from "@/components/ui/prefect-logo";

interface LoginPageProps {
	redirectTo?: string;
}

export function LoginPage({ redirectTo = "/dashboard" }: LoginPageProps) {
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [shouldRedirectAfterAuth, setShouldRedirectAfterAuth] = useState(false);
	const { login, isAuthenticated } = useAuth();
	const navigate = useNavigate();

	// Navigate to redirectTo only after the user explicitly submitted the
	// login form AND the auth context has propagated. Deferring to an effect
	// ensures the router's beforeLoad sees the updated auth state on the next
	// render, avoiding a race where navigate() runs against stale context and
	// bounces back to /login.
	useEffect(() => {
		if (shouldRedirectAfterAuth && isAuthenticated) {
			void navigate({ to: redirectTo });
		}
	}, [shouldRedirectAfterAuth, isAuthenticated, navigate, redirectTo]);

	const handleSubmit = (e: FormEvent) => {
		e.preventDefault();
		if (isSubmitting || !password.trim()) return;

		setIsSubmitting(true);
		setError("");

		void login(password).then((result) => {
			if (result.success) {
				setShouldRedirectAfterAuth(true);
			} else {
				setError(result.error ?? "Authentication failed");
				setIsSubmitting(false);
			}
		});
	};

	return (
		<div className="flex items-center justify-center min-h-screen">
			<Card className="w-full max-w-[400px]">
				<CardHeader className="flex flex-col items-center gap-4">
					<PrefectLogo className="size-16" />
					<CardTitle>Login</CardTitle>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleSubmit} className="flex flex-col gap-4">
						<Input
							type="password"
							placeholder="admin:pass"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							autoFocus
							disabled={isSubmitting}
						/>
						{error && <p className="text-sm text-destructive">{error}</p>}
						<Button type="submit" disabled={isSubmitting} className="w-full">
							{isSubmitting ? "Logging in..." : "Login"}
						</Button>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
