export const isSendKey = event => event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
