import { createSlice } from '@reduxjs/toolkit'

const initialState = {
  enableRag: true,
  ttsVoice: 'en', // 'en' | 'ru'
  chunkMs: 300,   // 200-500 ms
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
  },
})

export const { setEnableRag, setTtsVoice, setChunkMs } = settingsSlice.actions
export default settingsSlice.reducer
