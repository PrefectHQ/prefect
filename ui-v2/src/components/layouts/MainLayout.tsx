import { AppSidebar } from "@/components/ui/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { useColorMode } from "@/hooks/use-color-mode";
import { ThemeProvider } from "../ui/theme-provider";

export function MainLayout({ children }: { children: React.ReactNode }) {
	// Initialize color mode class on document.body
	useColorMode();

	return (
		<ThemeProvider
			attribute="class"
			defaultTheme="system"
			enableSystem
			disableTransitionOnChange
			storageKey="vite-ui-theme"
		>
			<SidebarProvider>
				<AppSidebar />
				<main className="flex-1 overflow-auto p-4">{children}</main>
				<Toaster />
			</SidebarProvider>
		</ThemeProvider>
	);
}
