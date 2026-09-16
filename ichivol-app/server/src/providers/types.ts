export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ProviderChatResult {
  text: string
  model: string
  provider: string
}

export interface LlmProvider {
  name: 'anthropic' | 'openai' | 'openrouter'
  chat(messages: ChatMessage[], opts?: { maxTokens?: number }): Promise<ProviderChatResult>
}
