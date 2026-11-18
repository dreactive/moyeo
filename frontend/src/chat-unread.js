// Count messages from other people that arrived after the last one seen in the chat bubble.
export function unreadCount(messages,seenId,userId) {
  if (seenId === null) return 0;
  const index = messages.findIndex(message => message.id === seenId);
  if (index < 0) return 0;
  return messages.slice(index + 1).filter(message => message.author_id !== userId).length;
}
