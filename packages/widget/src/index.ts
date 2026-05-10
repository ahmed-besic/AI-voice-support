import {
	ActivityHandling,
	EndSensitivity,
	GoogleGenAI,
	Modality,
	StartSensitivity,
} from "@google/genai";
import {
	policyControlEventSchema,
	type PolicyControlEvent,
	toolExecutionRequestSchema,
	type ToolExecutionResponse,
	userTurnRequestSchema,
	userTurnResponseSchema,
	voiceSessionBootstrapSchema,
	type WidgetPublicConfig,
	type WidgetSessionConfig,
	widgetPublicConfigSchema,
	widgetSessionConfigSchema,
	widgetEventSchema,
} from "@voice-support/contracts";
import { AudioPlaybackQueue, MicStreamer } from "./audio";
import {
	applyThemeVariables,
	type WidgetThemeName,
} from "./themes";
import { collectInlineAudioParts, formatRemaining } from "./utils";

export type WidgetInitOptions = {
	apiBaseUrl: string;
	siteId: string;
	mount?: HTMLElement;
	title?: string;
	welcomeMessage?: string;
	theme?: WidgetThemeName;
};

type LiveSession = Awaited<ReturnType<GoogleGenAI["live"]["connect"]>>;

type LiveMessage = {
	serverContent?: {
		turnComplete?: boolean;
		interrupted?: boolean;
		inputTranscription?: { text?: string };
		outputTranscription?: { text?: string };
	};
	usageMetadata?: {
		promptTokenCount?: number;
		candidatesTokenCount?: number;
		audioInputDurationSeconds?: number;
		audioOutputDurationSeconds?: number;
	};
	toolCall?: {
		functionCalls?: Array<{
			id: string;
			name: string;
			args?: Record<string, unknown>;
		}>;
	};
};

const ROLE_ASSISTANT = "assistant" as const;
const ROLE_USER = "user" as const;
type SpeakerRole = typeof ROLE_USER | typeof ROLE_ASSISTANT;
type StreamingPhase = "partial" | "final";
type VoiceUiState = "idle" | "connecting" | "active";

type WidgetState = {
	sessionId: string | null;
	sessionJwt: string | null;
	liveSession: LiveSession | null;
	mic: MicStreamer | null;
	playback: AudioPlaybackQueue;
	mode: "voice" | "text";
	status: string;
	reconnectAttempts: number;
	countdownTimer: number | null;
	sessionDeadlineMs: number | null;
	warningShown: boolean;
	sequenceCounter: number;
	draftMessages: Partial<Record<SpeakerRole, HTMLDivElement>>;
	draftSequences: Partial<Record<SpeakerRole, number>>;
	voiceState: VoiceUiState;
	voiceControlVersion: number;
	theme: WidgetThemeName;
	defaultMode: "voice" | "text";
	voiceEnabled: boolean;
	textEnabled: boolean;
	countdownWarningSeconds: number;
	controlStream: EventSource | null;
	inputsLocked: boolean;
	strictBehaviorEnabled: boolean;
};

const STYLE = `
.voice-support-widget{position:fixed;right:20px;bottom:20px;z-index:9999;font-family:var(--voice-support-font-family);color:var(--voice-support-text-color);-webkit-font-smoothing:antialiased;display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.voice-support-panel{width:min(380px,calc(100vw - 24px));background:var(--voice-support-panel-bg);border:1px solid var(--voice-support-panel-border);border-radius:12px;box-shadow:var(--voice-support-panel-shadow);display:none;max-height:520px;display:flex;flex-direction:column;overflow:hidden}
.voice-support-panel[hidden]{display:none}
.voice-support-panel:not([hidden]){display:flex;flex-direction:column}
.voice-support-header{padding:12px 12px 10px;border-bottom:1px solid var(--voice-support-header-border);display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.voice-support-header-copy{min-width:0;flex:1}
.voice-support-header strong{display:block;font-size:.875rem;font-weight:500;color:var(--voice-support-title-color);letter-spacing:-.01em}
.voice-support-header span{display:block;font-size:.75rem;color:var(--voice-support-subtitle-color);margin-top:2px;line-height:1.3}
.voice-support-icon-btn{appearance:none;border:0;background:transparent;color:var(--voice-support-icon-color);cursor:pointer;font-size:1rem;line-height:1;padding:0;min-width:20px;min-height:20px;display:inline-flex;align-items:center;justify-content:center;transition:color .15s}
.voice-support-icon-btn:hover{color:var(--voice-support-icon-hover-color)}
.voice-support-body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:10px;flex:1;min-height:0}
.voice-support-log{flex:1;min-height:0;overflow:auto;padding:4px 0;display:grid;gap:2px}
.voice-support-msg{padding:8px 0;max-width:92%;line-height:1.55;font-size:.875rem}
.voice-support-msg.user{margin-left:auto;color:var(--voice-support-user-color);text-align:right}
.voice-support-msg.assistant{color:var(--voice-support-assistant-color)}
.voice-support-msg.system{color:var(--voice-support-system-color);font-size:.8125rem}
.voice-support-controls{display:flex;gap:6px;align-items:center}
.voice-support-btn{appearance:none;border:1px solid var(--voice-support-button-border);background:transparent;color:var(--voice-support-button-text);min-height:36px;padding:0 14px;font-size:.8125rem;font-weight:500;cursor:pointer;transition:border-color .15s,color .15s}
.voice-support-btn:hover{border-color:var(--voice-support-button-hover-border);color:var(--voice-support-button-hover-text)}
.voice-support-btn[data-action="voice"]{border-color:var(--voice-support-voice-button-border);color:var(--voice-support-voice-button-text)}
.voice-support-btn[data-action="voice"]:hover{border-color:var(--voice-support-voice-button-hover-border)}
.voice-support-btn[disabled]{opacity:.6;cursor:default}
.voice-support-status{font-size:.75rem;color:var(--voice-support-status-color);display:flex;justify-content:flex-end;align-items:center;gap:12px}
.voice-support-controls-row{display:flex;justify-content:space-between;align-items:center;gap:12px}
.voice-support-input{display:flex;gap:6px}
.voice-support-input input{flex:1;min-height:36px;border:1px solid var(--voice-support-input-border);background:transparent;color:var(--voice-support-input-text);padding:0 12px;font-size:.875rem;font-family:inherit;outline:none}
.voice-support-input input:focus{border-color:var(--voice-support-input-focus-border)}
.voice-support-input input::placeholder{color:var(--voice-support-input-placeholder)}
.voice-support-toggle{background:var(--voice-support-toggle-bg);color:var(--voice-support-toggle-text);border:1px solid var(--voice-support-toggle-border);padding:10px 16px;cursor:pointer;font-size:.8125rem;font-weight:500;transition:border-color .15s,color .15s,background-color .15s}
.voice-support-toggle:hover{border-color:var(--voice-support-toggle-hover-border);background:var(--voice-support-toggle-hover-bg);color:var(--voice-support-toggle-hover-text)}
.voice-support-live{display:inline-flex;align-items:center;gap:6px}
.voice-support-live::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--voice-support-live-dot)}
.voice-support-warning{color:var(--voice-support-warning-color)}
`;

export function initVoiceSupportWidget(options: WidgetInitOptions) {
	const mount = options.mount ?? document.body;
	const wrapper = document.createElement("div");
	wrapper.className = "voice-support-widget";
		const style = document.createElement("style");
		style.textContent = STYLE;
		applyThemeVariables(wrapper, options.theme ?? "graphite");
		const panel = document.createElement("section");
	panel.className = "voice-support-panel";
	panel.setAttribute("aria-live", "polite");

	const header = document.createElement("div");
	header.className = "voice-support-header";
	const headerCopy = document.createElement("div");
	headerCopy.className = "voice-support-header-copy";
	const headerTitle = document.createElement("strong");
	headerTitle.textContent = options.title ?? "Support assistant";
	const headerSubtitle = document.createElement("span");
	headerSubtitle.textContent =
		options.welcomeMessage ?? "Realtime help with safe fallback to text.";
	headerCopy.append(headerTitle, headerSubtitle);
	const closeButton = document.createElement("button");
	closeButton.className = "voice-support-icon-btn";
	closeButton.dataset.action = "close";
	closeButton.type = "button";
	closeButton.setAttribute("aria-label", "Close support assistant");
	closeButton.textContent = "×";
	header.append(headerCopy, closeButton);

	const body = document.createElement("div");
	body.className = "voice-support-body";

	const log = document.createElement("div");
	log.className = "voice-support-log";
	log.setAttribute("role", "log");
	log.setAttribute("aria-live", "polite");

	const status = document.createElement("div");
	status.className = "voice-support-status";
	const live = document.createElement("span");
	live.className = "voice-support-live";
	live.textContent = "Initializing";
	const timer = document.createElement("span");
	timer.className = "voice-support-timer";
	timer.textContent = "--:--";
	status.append(live, timer);

		const controls = document.createElement("div");
		controls.className = "voice-support-controls";
		const voiceButton = document.createElement("button");
	voiceButton.className = "voice-support-btn";
		voiceButton.dataset.action = "voice";
		voiceButton.type = "button";
		voiceButton.textContent = "Start voice";
		controls.append(voiceButton);

	const textForm = document.createElement("form");
	textForm.className = "voice-support-input";
	const textInput = document.createElement("input");
	textInput.type = "text";
	textInput.placeholder = "Type your question";
	textInput.setAttribute("aria-label", "Type your support question");
	const sendButton = document.createElement("button");
	sendButton.className = "voice-support-btn";
	sendButton.type = "submit";
	sendButton.textContent = "Send";
	textForm.append(textInput, sendButton);

	const controlsRow = document.createElement("div");
	controlsRow.className = "voice-support-controls-row";
	controlsRow.append(controls, status);
	body.append(log, controlsRow, textForm);
	panel.append(header, body);

	const toggleButton = document.createElement("button");
	toggleButton.className = "voice-support-toggle";
	toggleButton.setAttribute("aria-label", "Toggle support assistant");
	toggleButton.textContent = "Support";
	wrapper.append(style, panel, toggleButton);
	mount.append(wrapper);

	const liveLabel = live;
	const timerLabel = timer;

	const state: WidgetState = {
		sessionId: null,
		sessionJwt: null,
		liveSession: null,
		mic: null,
		playback: new AudioPlaybackQueue(),
		mode: "voice",
		status: "idle",
		reconnectAttempts: 0,
		countdownTimer: null,
		sessionDeadlineMs: null,
		warningShown: false,
		sequenceCounter: 0,
		draftMessages: {},
		draftSequences: {},
		voiceState: "idle",
		voiceControlVersion: 0,
		theme: options.theme ?? "graphite",
		defaultMode: "voice",
		voiceEnabled: true,
		textEnabled: true,
		countdownWarningSeconds: 60,
		controlStream: null,
		inputsLocked: false,
		strictBehaviorEnabled: true,
	};

	const nextSequence = () => {
		state.sequenceCounter += 1;
		return state.sequenceCounter;
	};

	const setStatus = (status: string, warning = false) => {
		state.status = status;
		liveLabel.textContent = status;
		liveLabel.classList.toggle("voice-support-warning", warning);
	};

	const setVoiceUiState = (voiceState: VoiceUiState) => {
		state.voiceState = voiceState;
		if (!state.voiceEnabled) {
			voiceButton.textContent = "Voice off";
			voiceButton.disabled = true;
			voiceButton.hidden = true;
			return;
		}
		voiceButton.hidden = false;
		if (state.inputsLocked) {
			voiceButton.textContent = "Locked";
			voiceButton.disabled = true;
			return;
		}
		if (voiceState === "active") {
			voiceButton.textContent = "Stop voice";
			voiceButton.disabled = false;
			return;
		}
		if (voiceState === "connecting") {
			voiceButton.textContent = "Connecting...";
			voiceButton.disabled = true;
			return;
		}
		voiceButton.textContent = "Start voice";
		voiceButton.disabled = false;
	};

	const setInputsLocked = (locked: boolean) => {
		state.inputsLocked = locked;
		textInput.disabled = locked || !state.textEnabled;
		sendButton.disabled = locked || !state.textEnabled;
		textForm.hidden = !state.textEnabled;
		if (locked) {
			voiceButton.textContent = "Locked";
			voiceButton.disabled = true;
		} else {
			setVoiceUiState(state.voiceState);
		}
	};

	const applyTheme = (themeName: WidgetThemeName) => {
		state.theme = themeName;
		applyThemeVariables(wrapper, themeName);
		wrapper.dataset.theme = themeName;
	};

	const closeControlStream = () => {
		state.controlStream?.close();
		state.controlStream = null;
	};

	const appendMessage = (
		role: "user" | "assistant" | "system",
		text: string,
	) => {
		const message = document.createElement("div");
		message.className = `voice-support-msg ${role}`;
		message.textContent = text;
		log.append(message);
		log.scrollTop = log.scrollHeight;
	};

	const finalizeDraftMessage = (role: SpeakerRole) => {
		const existing = state.draftMessages[role];
		if (!existing) {
			return;
		}
		existing.dataset.streaming = "false";
		delete state.draftMessages[role];
		delete state.draftSequences[role];
	};

	const mergeTranscriptText = (currentText: string, incomingText: string) => {
		if (!currentText) {
			return incomingText;
		}
		if (!incomingText || incomingText === currentText) {
			return currentText;
		}
		if (incomingText.startsWith(currentText)) {
			return incomingText;
		}
		const incomingInCurrent = currentText.includes(incomingText);
		const currentStartsWithIncoming = currentText.startsWith(incomingText);
		if (currentStartsWithIncoming || incomingInCurrent) {
			return currentText;
		}
		const currentHasNoTrailingSpace = !currentText.endsWith(" ");
		const incomingHasNoLeadingSpace = !incomingText.startsWith(" ");
		const incomingStartsWithPunctuation = /^[.,!?;:)]/.test(incomingText);
		const needsSpace =
			currentHasNoTrailingSpace &&
			incomingHasNoLeadingSpace &&
			!incomingStartsWithPunctuation;
		return `${currentText}${needsSpace ? " " : ""}${incomingText}`;
	};

	const renderStreamingMessage = (
		role: SpeakerRole,
		text: string,
		phase: StreamingPhase,
	) => {
		const isFinal = phase === "final";
		const existing = state.draftMessages[role];
		if (!existing) {
			const message = document.createElement("div");
			message.className = `voice-support-msg ${role}`;
			message.textContent = text;
			message.dataset.streaming = isFinal ? "false" : "true";
			log.append(message);
			log.scrollTop = log.scrollHeight;
			if (!isFinal) {
				state.draftMessages[role] = message;
			}
			return message.textContent ?? text;
		}

		const nextText = mergeTranscriptText(existing.textContent ?? "", text);
		existing.textContent = nextText;
		existing.dataset.streaming = isFinal ? "false" : "true";
		log.scrollTop = log.scrollHeight;
		if (isFinal) {
			delete state.draftMessages[role];
		}
		return nextText;
	};

	const sequenceForRole = (role: SpeakerRole, phase: StreamingPhase) => {
		const current = state.draftSequences[role] ?? nextSequence();
		state.draftSequences[role] = current;
		if (phase === "final") {
			delete state.draftSequences[role];
		}
		return current;
	};

	const sendWidgetEvent = async (event: unknown) => {
		if (!state.sessionJwt) {
			return;
		}
		const payload = widgetEventSchema.parse(event);
		await fetch(`${options.apiBaseUrl}/widget/events`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${state.sessionJwt}`,
			},
			body: JSON.stringify(payload),
		}).catch(() => undefined);
	};

	const sendUserTurnForModeration = async (
		text: string,
		source: "voice_input_transcription" | "text_input",
		sequence: number,
	) => {
		if (!state.sessionId || !state.sessionJwt) {
			return null;
		}
		const response = await fetch(
			`${options.apiBaseUrl}/widget/sessions/${state.sessionId}/turns`,
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${state.sessionJwt}`,
				},
				body: JSON.stringify(
					userTurnRequestSchema.parse({
						sessionId: state.sessionId,
						role: "user",
						text,
						source,
						sequence,
						final: true,
						timestamp: new Date().toISOString(),
					}),
				),
			},
		);
		if (!response.ok) {
			return null;
		}
		return userTurnResponseSchema.parse(await response.json());
	};

	const handlePolicyEvent = async (rawEvent: PolicyControlEvent) => {
		if (rawEvent.message) {
			appendMessage("system", rawEvent.message);
		}
		if (rawEvent.type === "policy_state" && rawEvent.terminated) {
			closeControlStream();
			await stopVoiceSession({ statusText: "Session terminated", warning: true });
			setInputsLocked(true);
			setStatus("Session terminated", true);
			return;
		}
		if (rawEvent.type === "policy_warning" || rawEvent.type === "policy_strike") {
			setStatus(
				`Policy warning ${rawEvent.currentStrikeCount}/${rawEvent.maxStrikes}`,
				true,
			);
		}
		if (rawEvent.type === "policy_terminated") {
			closeControlStream();
			await stopVoiceSession({ statusText: "Session terminated", warning: true });
			setInputsLocked(true);
			setStatus("Session terminated", true);
		}
	};

	const openControlStream = (controlStreamUrl: string) => {
		if (!state.strictBehaviorEnabled || typeof EventSource === "undefined") {
			return;
		}
		closeControlStream();
		const eventSource = new EventSource(controlStreamUrl);
		state.controlStream = eventSource;
		const attach = (eventType: PolicyControlEvent["type"]) => {
			eventSource.addEventListener(eventType, (event) => {
				const payload = policyControlEventSchema.parse(
					JSON.parse((event as MessageEvent<string>).data),
				);
				void handlePolicyEvent(payload);
			});
		};
		attach("policy_state");
		attach("policy_warning");
		attach("policy_strike");
		attach("policy_terminated");
	};

	const applySessionConfig = (
		config: Pick<
			WidgetSessionConfig,
			| "defaultMode"
			| "voiceEnabled"
			| "textEnabled"
			| "strictBehaviorEnabled"
			| "theme"
			| "ui"
		>,
	) => {
		state.defaultMode = config.defaultMode;
		state.voiceEnabled = config.voiceEnabled;
		state.textEnabled = config.textEnabled;
		state.strictBehaviorEnabled = config.strictBehaviorEnabled;
		state.countdownWarningSeconds = config.ui.countdownWarningSeconds;
		if (!options.theme) {
			applyTheme(config.theme);
		}
		if (!options.title) {
			headerTitle.textContent = config.ui.title;
		}
		if (!options.welcomeMessage) {
			headerSubtitle.textContent = config.ui.welcomeMessage;
			const firstAssistant = log.querySelector(
				".voice-support-msg.assistant",
			) as HTMLDivElement | null;
			if (firstAssistant && log.childElementCount === 1) {
				firstAssistant.textContent = config.ui.welcomeMessage;
			}
		}
		setInputsLocked(state.inputsLocked);
		setVoiceUiState(state.voiceState);
	};

	const loadInitialConfig = async () => {
		try {
			const response = await fetch(
				`${options.apiBaseUrl}/widget/sites/${options.siteId}/settings`,
				{
					method: "GET",
				},
			);
			if (!response.ok) {
				return;
			}
			const config: WidgetPublicConfig = widgetPublicConfigSchema.parse(
				await response.json(),
			);
			applySessionConfig(config);
		} catch {
			// Leave the widget on its local defaults if the public config cannot be fetched.
		}
	};

	const updateTimer = () => {
		if (!state.sessionDeadlineMs) {
			timerLabel.textContent = "--:--";
			return;
		}
		const remainingSeconds = Math.max(
			0,
			(state.sessionDeadlineMs - Date.now()) / 1000,
		);
		timerLabel.textContent = formatRemaining(remainingSeconds);
		if (
			remainingSeconds <= state.countdownWarningSeconds &&
			!state.warningShown
		) {
			state.warningShown = true;
			appendMessage(
				"system",
				`Voice mode will switch to text in about ${state.countdownWarningSeconds} seconds unless the session ends first.`,
			);
			setStatus("Session ending soon", true);
		}
		if (remainingSeconds <= 0) {
			void fallbackToText("max_duration_reached");
		}
	};

	const startCountdown = (maxSeconds: number) => {
		state.sessionDeadlineMs = Date.now() + maxSeconds * 1000;
		state.warningShown = false;
		if (state.countdownTimer) {
			window.clearInterval(state.countdownTimer);
		}
		updateTimer();
		state.countdownTimer = window.setInterval(updateTimer, 1000);
	};

	const stopCountdown = () => {
		if (state.countdownTimer) {
			window.clearInterval(state.countdownTimer);
			state.countdownTimer = null;
		}
		state.sessionDeadlineMs = null;
		timerLabel.textContent = "--:--";
	};

	const executeToolCall = async (functionCall: {
		id: string;
		name: string;
		args?: Record<string, unknown>;
	}) => {
		if (!state.sessionId || !state.sessionJwt) {
			return;
		}
		const response = await fetch(`${options.apiBaseUrl}/widget/tools/execute`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${state.sessionJwt}`,
			},
			body: JSON.stringify(
				toolExecutionRequestSchema.parse({
					sessionId: state.sessionId,
					toolName: functionCall.name,
					callId: functionCall.id,
					args: functionCall.args ?? {},
				}),
			),
		});
		const body = (await response.json()) as ToolExecutionResponse;
		state.liveSession?.sendToolResponse?.({
			functionResponses: [
				{
					id: body.callId,
					name: body.toolName,
					response: (body.output ?? {}) as Record<string, unknown>,
				},
			],
		});
	};

		const processPlaybackError = () => {
			setStatus("Voice playback failed, switching to text", true);
			void fallbackToText("fallback_to_text");
		};

		const stopVoiceSession = async ({
			keepPanelOpen = true,
			statusText = "Text chat active",
			warning = false,
		}: {
			keepPanelOpen?: boolean;
			statusText?: string;
			warning?: boolean;
		} = {}) => {
			state.voiceControlVersion += 1;
			setVoiceUiState("idle");
			state.mode = "text";
			closeControlStream();
			finalizeDraftMessage(ROLE_ASSISTANT);
			finalizeDraftMessage(ROLE_USER);
			const session = state.liveSession;
			state.liveSession = null;
			const mic = state.mic;
			state.mic = null;
			try {
				session?.sendRealtimeInput?.({ audioStreamEnd: true });
			} catch {
				// Ignore best-effort close errors during manual shutdown.
			}
			session?.close?.();
			await mic?.stop();
			state.playback.clear();
			if (!keepPanelOpen) {
				panel.hidden = true;
			}
			setStatus(statusText, warning);
		};

	const handleLiveMessage = (message: unknown) => {
		const liveMessage = message as LiveMessage;
		const turnComplete = Boolean(liveMessage.serverContent?.turnComplete);
		if (liveMessage.serverContent?.interrupted) {
			state.playback.clear();
			setStatus("Interrupted");
		}

		const audioParts = collectInlineAudioParts(liveMessage);
		for (const audioPart of audioParts) {
			void state.playback.enqueue(audioPart).catch(() => {
				processPlaybackError();
			});
		}

		const pendingTasks: Promise<unknown>[] = [];
		const inputTranscript = liveMessage.serverContent?.inputTranscription?.text;
		if (inputTranscript) {
			finalizeDraftMessage(ROLE_ASSISTANT);
			const phase: StreamingPhase = turnComplete ? "final" : "partial";
			const sequence = sequenceForRole(ROLE_USER, phase);
			const renderedText = renderStreamingMessage(
				ROLE_USER,
				inputTranscript,
				phase,
			);
			pendingTasks.push(
				sendWidgetEvent({
					type: "transcript",
					payload: {
						sessionId: state.sessionId,
						role: ROLE_USER,
						text: renderedText,
						final: phase === "final",
						sequence,
						source: "input_transcription",
					},
				}),
			);
			if (phase === "final") {
				pendingTasks.push(
					sendUserTurnForModeration(
						renderedText,
						"voice_input_transcription",
						sequence,
					).then((result) => {
						if (!state.controlStream && result?.policyEvent) {
							return handlePolicyEvent(result.policyEvent);
						}
						return undefined;
					}),
				);
			}
		}
		const outputTranscript =
			liveMessage.serverContent?.outputTranscription?.text;
		if (outputTranscript) {
			finalizeDraftMessage(ROLE_USER);
			const phase: StreamingPhase = turnComplete ? "final" : "partial";
			const renderedText = renderStreamingMessage(
				ROLE_ASSISTANT,
				outputTranscript,
				phase,
			);
			pendingTasks.push(
				sendWidgetEvent({
					type: "transcript",
					payload: {
						sessionId: state.sessionId,
						role: ROLE_ASSISTANT,
						text: renderedText,
						final: phase === "final",
						sequence: sequenceForRole(ROLE_ASSISTANT, phase),
						source: "output_transcription",
					},
				}),
			);
		}
		if (liveMessage.usageMetadata) {
			pendingTasks.push(
				sendWidgetEvent({
					type: "usage",
					payload: {
						sessionId: state.sessionId,
						inputTokens: liveMessage.usageMetadata.promptTokenCount ?? 0,
						outputTokens: liveMessage.usageMetadata.candidatesTokenCount ?? 0,
						audioInputSeconds:
							liveMessage.usageMetadata.audioInputDurationSeconds ?? 0,
						audioOutputSeconds:
							liveMessage.usageMetadata.audioOutputDurationSeconds ?? 0,
					},
				}),
			);
		}
		const functionCalls = liveMessage.toolCall?.functionCalls ?? [];
		void (async () => {
			if (pendingTasks.length > 0) {
				await Promise.allSettled(pendingTasks);
			}
			for (const functionCall of functionCalls) {
				await executeToolCall(functionCall);
			}
		})();
	};

		const connectLive = async (controlVersion: number) => {
		const bootstrapResponse = await fetch(
			`${options.apiBaseUrl}/widget/bootstrap`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(
					voiceSessionBootstrapSchema.parse({
						siteId: options.siteId,
						requestedMode: "voice",
						widgetVersion: "0.1.0",
					}),
				),
			},
		);
		if (!bootstrapResponse.ok) {
			throw new Error(`Bootstrap failed: ${bootstrapResponse.status}`);
		}
		const config: WidgetSessionConfig = widgetSessionConfigSchema.parse(
			await bootstrapResponse.json(),
		);
		state.sessionId = config.sessionId;
		state.sessionJwt = config.sessionJwt;
		applySessionConfig(config);
		setInputsLocked(false);
		state.mode = "voice";
		startCountdown(config.maxSessionDurationSeconds);
		openControlStream(config.controlStreamUrl);
		if (!config.voiceEnabled) {
			throw new Error("Voice mode is disabled for this site");
		}
		await state.playback.initialize();
		const ai = new GoogleGenAI({
			apiKey: config.ephemeralToken,
			httpOptions: { apiVersion: "v1alpha" },
		});
			const session = await ai.live.connect({
				model: config.realtimeModel,
				callbacks: {
					onopen: async () => {
						setStatus("Live voice connected");
						setVoiceUiState("active");
						await sendWidgetEvent({
							type: "connection_state",
							payload: { sessionId: config.sessionId, state: "open" },
						});
					},
				onmessage: (message: unknown) => {
					void handleLiveMessage(message);
				},
				onerror: async (error: ErrorEvent) => {
					const detail = error.message || "Live connection error";
					setStatus(`Voice error: ${detail}`, true);
					await sendWidgetEvent({
						type: "connection_state",
						payload: { sessionId: config.sessionId, state: "error", detail },
					});
					await fallbackToText("socket_error");
				},
				onclose: async () => {
					await sendWidgetEvent({
						type: "connection_state",
						payload: { sessionId: config.sessionId, state: "closed" },
					});
				},
			},
			config: {
				responseModalities: [Modality.AUDIO],
				inputAudioTranscription: {},
				outputAudioTranscription: {},
				realtimeInputConfig: {
					activityHandling: ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
					automaticActivityDetection: {
						disabled: config.vadConfig.disabled,
						startOfSpeechSensitivity:
							config.vadConfig.startOfSpeechSensitivity ===
							"START_SENSITIVITY_HIGH"
								? StartSensitivity.START_SENSITIVITY_HIGH
								: StartSensitivity.START_SENSITIVITY_LOW,
						endOfSpeechSensitivity:
							config.vadConfig.endOfSpeechSensitivity === "END_SENSITIVITY_HIGH"
								? EndSensitivity.END_SENSITIVITY_HIGH
								: EndSensitivity.END_SENSITIVITY_LOW,
						prefixPaddingMs: config.vadConfig.prefixPaddingMs,
						silenceDurationMs: config.vadConfig.silenceDurationMs,
					},
				},
				},
			});
			if (controlVersion !== state.voiceControlVersion) {
				session.close?.();
				return;
			}
			state.liveSession = session;
			state.mic = new MicStreamer();
			await state.mic.start((audioData) => {
				state.liveSession?.sendRealtimeInput?.({
					audio: {
						data: audioData,
						mimeType: "audio/pcm;rate=16000",
					},
				});
			});
			if (controlVersion !== state.voiceControlVersion) {
				await stopVoiceSession({ statusText: "Voice stopped" });
			}
		};

	const ensureTextSession = async () => {
		if (state.sessionId && state.sessionJwt) {
			return;
		}
		const bootstrapResponse = await fetch(
			`${options.apiBaseUrl}/widget/bootstrap`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(
					voiceSessionBootstrapSchema.parse({
						siteId: options.siteId,
						requestedMode: "text",
						widgetVersion: "0.1.0",
					}),
				),
			},
		);
		if (!bootstrapResponse.ok) {
			throw new Error(`Text bootstrap failed: ${bootstrapResponse.status}`);
		}
		const config: WidgetSessionConfig = widgetSessionConfigSchema.parse(
			await bootstrapResponse.json(),
		);
		state.sessionId = config.sessionId;
		state.sessionJwt = config.sessionJwt;
		applySessionConfig(config);
		setInputsLocked(false);
		state.mode = "text";
		startCountdown(config.maxSessionDurationSeconds);
	};

		const sendTextTurn = async (text: string) => {
			if (!state.sessionId || !state.sessionJwt) {
				await ensureTextSession();
			}
			finalizeDraftMessage(ROLE_ASSISTANT);
			finalizeDraftMessage(ROLE_USER);
			appendMessage("user", text);
		await sendWidgetEvent({
			type: "transcript",
			payload: {
				sessionId: state.sessionId,
				role: "user",
				text,
				final: true,
				sequence: nextSequence(),
				source: "text_fallback",
			},
		});
		const response = await fetch(`${options.apiBaseUrl}/widget/text-turn`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${state.sessionJwt}`,
			},
			body: JSON.stringify({ sessionId: state.sessionId, text }),
		});
		if (!response.ok) {
			throw new Error(`Text request failed: ${response.status}`);
		}
		const payload = (await response.json()) as {
			text: string;
			terminated?: boolean;
			policyEvent?: unknown;
		};
		finalizeDraftMessage(ROLE_ASSISTANT);
		appendMessage("assistant", payload.text);
		if (payload.policyEvent) {
			const policyEvent = policyControlEventSchema.parse(payload.policyEvent);
			await handlePolicyEvent(policyEvent);
		}
	};

		const fallbackToText = async (
			reason: "max_duration_reached" | "fallback_to_text" | "socket_error",
		) => {
			if (state.mode === "text") {
				return;
			}
			if (!state.textEnabled) {
				await stopVoiceSession({
					statusText: "Voice session ended",
					warning: reason !== "fallback_to_text",
				});
				appendMessage("system", "Text mode is disabled for this site.");
				return;
			}
			await stopVoiceSession({
				statusText: "Text fallback active",
				warning: reason !== "fallback_to_text",
			});
			await ensureTextSession();
			await sendWidgetEvent({
				type: "session_end",
				payload: { sessionId: state.sessionId, reason },
			});
		};

		const startVoice = async () => {
			const controlVersion = state.voiceControlVersion + 1;
			state.voiceControlVersion = controlVersion;
			setVoiceUiState("connecting");
			try {
				appendMessage("system", "Connecting voice session...");
				setStatus("Connecting");
				await connectLive(controlVersion);
			} catch (error) {
				if (controlVersion !== state.voiceControlVersion) {
					return;
				}
				const detail =
					error instanceof Error
						? error.message
						: "Unknown voice connection error";
				appendMessage(
					"system",
					state.textEnabled
						? "Voice mode was unavailable, so the widget switched to text."
						: "Voice mode was unavailable for this site.",
				);
				setStatus(`Voice unavailable: ${detail}`, true);
				setVoiceUiState("idle");
				if (state.textEnabled) {
					await fallbackToText("fallback_to_text");
				}
			}
		};

		const shutdown = async (
			reason: "completed" | "user_closed" = "user_closed",
		) => {
			finalizeDraftMessage("assistant");
			finalizeDraftMessage("user");
			await stopVoiceSession({ statusText: "Closed" });
			stopCountdown();
			await state.playback.destroy();
			if (state.sessionId && state.sessionJwt) {
				await sendWidgetEvent({
					type: "session_end",
					payload: { sessionId: state.sessionId, reason },
				});
			}
		};

		panel
			.querySelector('[data-action="voice"]')
			?.addEventListener("click", () => {
				if (!state.voiceEnabled) {
					return;
				}
				if (state.voiceState === "active" || state.voiceState === "connecting") {
					void stopVoiceSession({ statusText: "Voice stopped" });
					return;
				}
				void startVoice();
			});
		panel
			.querySelector('[data-action="close"]')
			?.addEventListener("click", () => {
				void stopVoiceSession({
					keepPanelOpen: false,
					statusText: "Ready",
				});
			});
		toggleButton.addEventListener("click", () => {
			if (!panel.hidden) {
				void stopVoiceSession({
					keepPanelOpen: false,
					statusText: "Ready",
				});
				return;
			}
			panel.hidden = false;
		});

	textForm.addEventListener("submit", (event) => {
		event.preventDefault();
		if (state.inputsLocked || !state.textEnabled) {
			return;
		}
		const text = textInput.value.trim();
		if (!text) {
			return;
		}
		textInput.value = "";
		void sendTextTurn(text).catch((error) => {
			const detail =
				error instanceof Error ? error.message : "Message send failed";
			appendMessage("system", "Message could not be sent. Please try again.");
			setStatus(`Send failed: ${detail}`, true);
		});
	});

	appendMessage(
		"assistant",
		options.welcomeMessage ?? "How can I help you today?",
	);
	applyTheme(state.theme);
	setStatus("Ready");
	setVoiceUiState("idle");
	void loadInitialConfig();

	return {
		destroy() {
			void shutdown("user_closed");
			wrapper.remove();
		},
		setTheme(theme: WidgetThemeName) {
			applyTheme(theme);
		},
		getTheme() {
			return state.theme;
		},
	};
}
