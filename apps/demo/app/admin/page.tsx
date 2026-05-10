async function fetchJson<T>(path: string): Promise<T | null> {
	try {
		const response = await fetch(
			`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}${path}`,
			{
				cache: "no-store",
			},
		);
		if (!response.ok) {
			return null;
		}
		return (await response.json()) as T;
	} catch {
		return null;
	}
}

type SiteSummary = {
	site_id: string;
	display_name: string;
	active_sessions: number;
	daily_sessions: number;
	monthly_estimated_cost: number;
	monthly_budget: number;
};

type SessionRow = {
	id: string;
	status: string;
	mode: string;
	estimated_cost: number;
	created_at: string;
};

export default async function AdminPage() {
	const siteId = process.env.NEXT_PUBLIC_SITE_ID ?? "demo-site";
	const sites = await fetchJson<SiteSummary[]>("/admin/sites");
	const sessions = await fetchJson<SessionRow[]>(
		`/admin/sites/${siteId}/sessions`,
	);

	return (
		<main>
			<section className="admin-header">
				<span className="hero-label">Operator console</span>
				<h1>Monitor limits, transcripts, and cost signals.</h1>
				<p>
					Site-level budget tracking and recent sessions so operators can keep a
					tight rein on spend while letting teams embed the widget anywhere.
				</p>
			</section>

			<section>
				<h2
					style={{
						fontSize: "0.75rem",
						textTransform: "uppercase",
						letterSpacing: "0.14em",
						color: "var(--ink-tertiary)",
						fontWeight: 500,
						marginBottom: "1.5rem",
					}}
				>
					Sites
				</h2>
				{sites && sites.length > 0 ? (
					<table className="site-table">
						<thead>
							<tr>
								<th>Name</th>
								<th>Active</th>
								<th>Today</th>
								<th>Cost / Budget</th>
							</tr>
						</thead>
						<tbody>
							{sites.map((site) => (
								<tr key={site.site_id}>
									<td>{site.display_name}</td>
									<td>{site.active_sessions}</td>
									<td>{site.daily_sessions}</td>
									<td>
										${site.monthly_estimated_cost.toFixed(2)} / $
										{site.monthly_budget.toFixed(2)}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				) : (
					<p className="empty-state">
						API not running yet. Start the backend to load live site metrics.
					</p>
				)}
			</section>

			<section>
				<h2
					style={{
						fontSize: "0.75rem",
						textTransform: "uppercase",
						letterSpacing: "0.14em",
						color: "var(--ink-tertiary)",
						fontWeight: 500,
						marginBottom: "1.5rem",
					}}
				>
					Recent sessions
				</h2>
				{sessions && sessions.length > 0 ? (
					<>
						<div className="session-header">
							<span>Time</span>
							<span>Mode</span>
							<span>Status</span>
							<span>Cost</span>
						</div>
						<ul className="session-list">
							{sessions.map((session) => (
								<li key={session.id} className="session-item">
									<span>{new Date(session.created_at).toLocaleString()}</span>
									<span>{session.mode}</span>
									<span>{session.status}</span>
									<span>${session.estimated_cost.toFixed(2)}</span>
								</li>
							))}
						</ul>
					</>
				) : (
					<p className="empty-state">No sessions captured yet.</p>
				)}
			</section>
		</main>
	);
}
