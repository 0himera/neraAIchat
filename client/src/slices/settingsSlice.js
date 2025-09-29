import { createSlice } from '@reduxjs/toolkit'

const initialState = {
  enableRag: true,
  ttsVoice: 'en', // 'en' | 'ru'
  chunkMs: 300,   // 200-500 ms
  voiceMode: false,
  ttsSpeed: 1,
  speechQueue: [],
  systemPrompt: '',
  memoryNotes: '',
}

const settingsSlice = createSlice({
  name: 'settings',
  initialState,
  reducers: {
    setEnableRag(state, action) {
      state.enableRag = !!action.payload
    },
    setTtsVoice(state, action) {
      state.ttsVoice = action.payload || 'en'
    },
    setChunkMs(state, action) {
      const v = Number(action.payload)
      if (!Number.isNaN(v) && v >= 100 && v <= 1000) state.chunkMs = v
    },
    setVoiceMode(state, action) {
      const enabled = !!action.payload
      state.voiceMode = enabled
      if (!enabled) {
        state.speechQueue = []
      }
    },
    setTtsSpeed(state, action) {
      const val = Number(action.payload)
      if (!Number.isNaN(val)) {
        const clamped = Math.min(2, Math.max(0.5, val))
        state.ttsSpeed = clamped
      }
    },
    enqueueSpeech(state, action) {
      const payload = action.payload
      if (!payload || !payload.id || !payload.text) return
      // Avoid duplicate consecutive entries for same id
      const alreadyQueued = state.speechQueue.some(item => item.id === payload.id)
      if (!alreadyQueued) {
        state.speechQueue.push({ id: payload.id, text: payload.text })
      }
    },
    shiftSpeech(state) {
      state.speechQueue.shift()
    },
    setSystemPrompt(state, action) {
      state.systemPrompt = action.payload ?? ''
    },
    setMemoryNotes(state, action) {
      state.memoryNotes = action.payload ?? ''
    },
  },
})

export const {
  setEnableRag,
  setTtsVoice,
  setChunkMs,
  setVoiceMode,
  setTtsSpeed,
  enqueueSpeech,
  shiftSpeech,
  setSystemPrompt,
  setMemoryNotes,
} = settingsSlice.actions

export default settingsSlice.reducer
