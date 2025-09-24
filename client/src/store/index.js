import { configureStore } from '@reduxjs/toolkit'
import chatReducer from '../slices/chatSlice.js'
import settingsReducer from '../slices/settingsSlice.js'
import sessionsReducer from '../slices/sessionsSlice.js'

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    settings: settingsReducer,
    sessions: sessionsReducer,
  },
})
