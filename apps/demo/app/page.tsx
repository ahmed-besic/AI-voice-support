import Link from "next/link";
import { WidgetHost } from "../components/WidgetHost";

export default function HomePage() {
	return (
		<main>
			<WidgetHost />
			<section className="hero">
				<span className="hero-label">Open-source voice support</span>
				<h1>Realtime support, built for any site.</h1>
				<p className="hero-description">
					A voice-first support assistant that connects directly to Gemini Live,
					falls back to text when needed, and gives operators full visibility
					into sessions and spend.
				</p>
				<Link className="cta" href="/admin">
					Operator console →
				</Link>
			</section>
			<section className="metrics">
				<div className="metric">
					<strong>8 min</strong>
					<span>
						Hard session cap with a 60-second warning and automatic text
						fallback.
					</span>
				</div>
				<div className="metric">
					<strong>Direct</strong>
					<span>
						Browser streams PCM16 audio to Gemini Live using short-lived
						ephemeral tokens.
					</span>
				</div>
				<div className="metric">
					<strong>Pluggable</strong>
					<span>
						Adapters connect FAQ retrieval and ticket creation without touching
						core runtime.
					</span>
				</div>
			</section>
			<section className="details">
				<div className="detail">
					<h2>What this demo includes</h2>
					<ul>
						<li>Origin-validated widget bootstrap</li>
						<li>Realtime voice mode with barge-in handling</li>
						<li>Fallback text chat through the backend</li>
						<li>Session transcripts and usage tracking</li>
					</ul>
				</div>
				<div className="detail">
					<h2>What to try</h2>
					<ul>
						<li>Deny microphone access to verify text fallback</li>
						<li>Interrupt the model mid-response to test barge-in</li>
						<li>Watch the admin console update with session and cost data</li>
					</ul>
				</div>
			</section>
		</main>
	);
}
