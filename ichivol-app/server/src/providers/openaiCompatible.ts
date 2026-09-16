import type { ChatMessage, LlmProvider, ProviderChatResult } from './types.js'

interface OpenAiCompatibleOptions {
  name: 'openai' | 'openrouter'
  baseUrl: string
  apiKey: string | undefined
  model: string
  extraHeaders?: Record<string, string>
}

export function createOpenAiCompatibleProvider(opts: OpenAiCompatibleOptions): LlmProvider {
  return {
    name: opts.name,
    async chat(messages: ChatMessage[], chatOpts): Promise<ProviderChatResult> {
      if (!opts.apiKey) {
        throw new Error(`Configurez votre clé LLM dans Paramètres (${opts.name})`)
      }

      const res = await fetch(`${opts.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          authorization: `Bearer ${opts.apiKey}`,
          ...opts.extraHeaders,
        },
        body: JSON.stringify({
          model: opts.model,
          max_tokens: chatOpts?.maxTokens ?? 1024,
          messages,
        }),
      })

      if (!res.ok) {
        const body = await res.text()
        throw new Error(`${opts.name} ${res.status}: ${body}`)
      }

      const data = (await res.json()) as {
        choices: { message: { content: string } }[]
        model: string
      }
      const text = data.choices[0]?.message?.content ?? ''

      return { text, model: data.model, provider: opts.name }
    },
  }
}
