import { createSlice, nanoid } from '@reduxjs/toolkit'

const initialState = {
  messages: [],
  partialAsr: '',
}

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addUserMessage: {
      reducer(state, action) {
        state.messages.push(action.payload)
      },
      prepare(text, id) {
        return {
          payload: {
            id: id || nanoid(),
            role: 'user',
            text,
            created_at: new Date().toISOString(),
          },
        }
      },
    },
    addAssistantMessage: {
      reducer(state, action) {
        state.messages.push(action.payload)
      },
      prepare(text, id) {
        return {
          payload: {
            id: id || nanoid(),
            role: 'assistant',
            text,
            created_at: new Date().toISOString(),
          },
        }
      },
    },
    setPartialAsr(state, action) {
      state.partialAsr = action.payload || ''
    },
    replaceLastAssistant(state, action) {
      // replace last assistant message text (for streaming)
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].role === 'assistant') {
          state.messages[i].text = action.payload
          return
        }
      }
    },
    setMessages(state, action) {
      state.messages = action.payload || []
    },
    clearMessages(state) {
      state.messages = []
      state.partialAsr = ''
    },
    upsertMessage(state, action) {
      const msg = action.payload
      if (!msg || !msg.id) return
      const idx = state.messages.findIndex(m => m.id === msg.id)
      if (idx >= 0) {
        state.messages[idx] = { ...state.messages[idx], ...msg }
      } else {
        state.messages.push(msg)
      }
    },
    updateMessage(state, action) {
      const { id, text } = action.payload || {}
      if (!id) return
      const msg = state.messages.find(m => m.id === id)
      if (!msg) return
      if (text !== undefined) msg.text = text
    },
  },
})

export const {
  addUserMessage,
  addAssistantMessage,
  setPartialAsr,
  replaceLastAssistant,
  setMessages,
  clearMessages,
  upsertMessage,
  updateMessage,
} = chatSlice.actions
export default chatSlice.reducer
