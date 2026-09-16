import type { ChatMessage, LlmProvider, ProviderChatResult } from './types.js'

export interface AnthropicProviderOptions {
  apiKey: string | undefined
  model: string
}

export function createAnthropicProvider(opts: AnthropicProviderOptions): LlmProvider {
  return {
    name: 'anthropic',
    async chat(messages: ChatMessage[], chatOpts): Promise<ProviderChatResult> {
      if (!opts.apiKey) {
        throw new Error('Configurez votre clé LLM dans Paramètres (Anthropic)')
      }
      const system = messages.find((m) => m.role === 'system')?.content
      const rest = messages
        .filter((m) => m.role !== 'system')
        .map((m) => ({ role: m.role, content: m.content }))

      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': opts.apiKey,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: opts.model,
          max_tokens: chatOpts?.maxTokens ?? 1024,
          system,
          messages: rest,
        }),
      })

      if (!res.ok) {
        const body = await res.text()
        throw new Error(`Anthropic ${res.status}: ${body}`)
      }

      const data = (await res.json()) as {
        content: { type: string; text?: string }[]
        model: string
      }
      const text = data.content
        .filter((c) => c.type === 'text' && c.text)
        .map((c) => c.text)
        .join('\n')

      return { text, model: data.model, provider: 'anthropic' }
    },
  }
}
