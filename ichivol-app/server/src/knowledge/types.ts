export interface KnowledgeChunk {
  docId: string
  title: string
  url: string
  tags: string[]
  text: string
}

export interface ScoredChunk {
  docId: string
  title: string
  url: string
  score: number
  text: string
}
