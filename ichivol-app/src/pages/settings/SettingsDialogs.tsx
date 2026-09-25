import { ConfirmDialog } from '../../components/ConfirmDialog'
import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function SettingsDialogs({ c }: { c: Ctrl }) {
  const {
    pendingClearLlm,
    setPendingClearLlm,
    setClearKey,
    setLlmApiKey,
    pendingClearTwelve,
    setPendingClearTwelve,
    setClearTwelveDataKey,
    setTwelveDataApiKey,
  } = c

  return (
    <>
      {pendingClearLlm && (
        <ConfirmDialog
          title="Effacer la clé LLM ?"
          body="La clé stockée en base sera supprimée à l’enregistrement. Irréversible tant que tu n’en resaisis pas une nouvelle."
          confirmLabel="Effacer"
          danger
          onConfirm={() => {
            setClearKey(true)
            setLlmApiKey('')
            setPendingClearLlm(false)
          }}
          onCancel={() => setPendingClearLlm(false)}
        />
      )}

      {pendingClearTwelve && (
        <ConfirmDialog
          title="Effacer la clé Twelve Data ?"
          body="Ta clé perso sera retirée à l’enregistrement — retour à la clé opérateur si configurée."
          confirmLabel="Effacer"
          danger
          onConfirm={() => {
            setClearTwelveDataKey(true)
            setTwelveDataApiKey('')
            setPendingClearTwelve(false)
          }}
          onCancel={() => setPendingClearTwelve(false)}
        />
      )}
    </>
  )
}
