import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/ui/app-sidebar";
import { Toaster } from "../ui/toaster";

export function MainLayout({ children }: { children: React.ReactNode }) {
	return (
		<SidebarProvider>
			<AppSidebar />
			<main className="flex-1 overflow-auto">{children}</main>
			<Toaster />
		</SidebarProvider>
	);
}
