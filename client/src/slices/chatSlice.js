import { createSlice, nanoid } from '@reduxjs/toolkit'

const initialState = {
  messages: [
    { id: nanoid(), role: 'system', text: 'Welcome! Use mic or type to chat. Upload PDFs to enable RAG.' },
  ],
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
      prepare(text) {
        return { payload: { id: nanoid(), role: 'user', text } }
      },
    },
    addAssistantMessage: {
      reducer(state, action) {
        state.messages.push(action.payload)
      },
      prepare(text) {
        return { payload: { id: nanoid(), role: 'assistant', text } }
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
  },
})

export const { addUserMessage, addAssistantMessage, setPartialAsr, replaceLastAssistant } = chatSlice.actions
export default chatSlice.reducer
