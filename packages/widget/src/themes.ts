export type WidgetThemeName = "graphite" | "sand" | "ocean";

type WidgetTheme = {
	fontFamily: string;
	textColor: string;
	panelBackground: string;
	panelBorder: string;
	panelShadow: string;
	headerBorder: string;
	titleColor: string;
	subtitleColor: string;
	iconColor: string;
	iconHoverColor: string;
	userMessageColor: string;
	assistantMessageColor: string;
	systemMessageColor: string;
	buttonBorder: string;
	buttonText: string;
	buttonHoverBorder: string;
	buttonHoverText: string;
	voiceButtonBorder: string;
	voiceButtonText: string;
	voiceButtonHoverBorder: string;
	statusColor: string;
	inputBorder: string;
	inputText: string;
	inputFocusBorder: string;
	inputPlaceholder: string;
	toggleBorder: string;
	toggleBackground: string;
	toggleText: string;
	toggleHoverBorder: string;
	toggleHoverBackground: string;
	toggleHoverText: string;
	liveDot: string;
	warningColor: string;
};

const THEMES: Record<WidgetThemeName, WidgetTheme> = {
	graphite: {
		fontFamily: '"SF Pro Text",-apple-system,"Segoe UI",Roboto,sans-serif',
		textColor: "#e5e5e5",
		panelBackground: "#0a0a0a",
		panelBorder: "#1f1f1f",
		panelShadow: "0 32px 64px rgba(0,0,0,.5)",
		headerBorder: "#1a1a1a",
		titleColor: "#fafafa",
		subtitleColor: "#737373",
		iconColor: "#737373",
		iconHoverColor: "#fafafa",
		userMessageColor: "#fafafa",
		assistantMessageColor: "#a1a1a1",
		systemMessageColor: "#525252",
		buttonBorder: "#262626",
		buttonText: "#a1a1a1",
		buttonHoverBorder: "#404040",
		buttonHoverText: "#e5e5e5",
		voiceButtonBorder: "#404040",
		voiceButtonText: "#fafafa",
		voiceButtonHoverBorder: "#525252",
		statusColor: "#525252",
		inputBorder: "#262626",
		inputText: "#e5e5e5",
		inputFocusBorder: "#404040",
		inputPlaceholder: "#404040",
		toggleBorder: "#262626",
		toggleBackground: "#0a0a0a",
		toggleText: "#a1a1a1",
		toggleHoverBorder: "#404040",
		toggleHoverBackground: "#141414",
		toggleHoverText: "#e5e5e5",
		liveDot: "#22c55e",
		warningColor: "#ef4444",
	},
	sand: {
		fontFamily: '"Avenir Next","Segoe UI",sans-serif',
		textColor: "#2b241d",
		panelBackground: "#fff8ef",
		panelBorder: "#e2cfbc",
		panelShadow: "0 30px 70px rgba(98,69,38,.18)",
		headerBorder: "#eadac9",
		titleColor: "#241912",
		subtitleColor: "#7a685b",
		iconColor: "#8c7868",
		iconHoverColor: "#241912",
		userMessageColor: "#241912",
		assistantMessageColor: "#6d5a4d",
		systemMessageColor: "#977f6d",
		buttonBorder: "#d8c4af",
		buttonText: "#6b5545",
		buttonHoverBorder: "#b99373",
		buttonHoverText: "#241912",
		voiceButtonBorder: "#a97045",
		voiceButtonText: "#241912",
		voiceButtonHoverBorder: "#8f5d39",
		statusColor: "#8e7865",
		inputBorder: "#d8c4af",
		inputText: "#2b241d",
		inputFocusBorder: "#a97045",
		inputPlaceholder: "#b29b87",
		toggleBorder: "#d8c4af",
		toggleBackground: "#fff8ef",
		toggleText: "#6b5545",
		toggleHoverBorder: "#b99373",
		toggleHoverBackground: "#f5eadc",
		toggleHoverText: "#241912",
		liveDot: "#2f8f5b",
		warningColor: "#c4583d",
	},
	ocean: {
		fontFamily: '"IBM Plex Sans","Segoe UI",sans-serif',
		textColor: "#d9ebf8",
		panelBackground: "#081824",
		panelBorder: "#163246",
		panelShadow: "0 28px 60px rgba(3,18,29,.45)",
		headerBorder: "#143044",
		titleColor: "#f3fbff",
		subtitleColor: "#79a8c4",
		iconColor: "#79a8c4",
		iconHoverColor: "#f3fbff",
		userMessageColor: "#f3fbff",
		assistantMessageColor: "#9cc5dd",
		systemMessageColor: "#5c8198",
		buttonBorder: "#20445c",
		buttonText: "#9cc5dd",
		buttonHoverBorder: "#2b5c78",
		buttonHoverText: "#f3fbff",
		voiceButtonBorder: "#3e8ab5",
		voiceButtonText: "#f3fbff",
		voiceButtonHoverBorder: "#58a7d6",
		statusColor: "#5c8198",
		inputBorder: "#20445c",
		inputText: "#d9ebf8",
		inputFocusBorder: "#58a7d6",
		inputPlaceholder: "#52748a",
		toggleBorder: "#20445c",
		toggleBackground: "#081824",
		toggleText: "#9cc5dd",
		toggleHoverBorder: "#2b5c78",
		toggleHoverBackground: "#0c2231",
		toggleHoverText: "#f3fbff",
		liveDot: "#33d1c6",
		warningColor: "#ff7b72",
	},
};

export const THEME_ORDER: WidgetThemeName[] = ["graphite", "sand", "ocean"];

export function applyThemeVariables(target: HTMLElement, themeName: WidgetThemeName): void {
	const theme = THEMES[themeName];
	target.style.setProperty("--voice-support-font-family", theme.fontFamily);
	target.style.setProperty("--voice-support-text-color", theme.textColor);
	target.style.setProperty("--voice-support-panel-bg", theme.panelBackground);
	target.style.setProperty("--voice-support-panel-border", theme.panelBorder);
	target.style.setProperty("--voice-support-panel-shadow", theme.panelShadow);
	target.style.setProperty("--voice-support-header-border", theme.headerBorder);
	target.style.setProperty("--voice-support-title-color", theme.titleColor);
	target.style.setProperty("--voice-support-subtitle-color", theme.subtitleColor);
	target.style.setProperty("--voice-support-icon-color", theme.iconColor);
	target.style.setProperty("--voice-support-icon-hover-color", theme.iconHoverColor);
	target.style.setProperty("--voice-support-user-color", theme.userMessageColor);
	target.style.setProperty("--voice-support-assistant-color", theme.assistantMessageColor);
	target.style.setProperty("--voice-support-system-color", theme.systemMessageColor);
	target.style.setProperty("--voice-support-button-border", theme.buttonBorder);
	target.style.setProperty("--voice-support-button-text", theme.buttonText);
	target.style.setProperty("--voice-support-button-hover-border", theme.buttonHoverBorder);
	target.style.setProperty("--voice-support-button-hover-text", theme.buttonHoverText);
	target.style.setProperty("--voice-support-voice-button-border", theme.voiceButtonBorder);
	target.style.setProperty("--voice-support-voice-button-text", theme.voiceButtonText);
	target.style.setProperty("--voice-support-voice-button-hover-border", theme.voiceButtonHoverBorder);
	target.style.setProperty("--voice-support-status-color", theme.statusColor);
	target.style.setProperty("--voice-support-input-border", theme.inputBorder);
	target.style.setProperty("--voice-support-input-text", theme.inputText);
	target.style.setProperty("--voice-support-input-focus-border", theme.inputFocusBorder);
	target.style.setProperty("--voice-support-input-placeholder", theme.inputPlaceholder);
	target.style.setProperty("--voice-support-toggle-border", theme.toggleBorder);
	target.style.setProperty("--voice-support-toggle-bg", theme.toggleBackground);
	target.style.setProperty("--voice-support-toggle-text", theme.toggleText);
	target.style.setProperty("--voice-support-toggle-hover-border", theme.toggleHoverBorder);
	target.style.setProperty("--voice-support-toggle-hover-bg", theme.toggleHoverBackground);
	target.style.setProperty("--voice-support-toggle-hover-text", theme.toggleHoverText);
	target.style.setProperty("--voice-support-live-dot", theme.liveDot);
	target.style.setProperty("--voice-support-warning-color", theme.warningColor);
}
