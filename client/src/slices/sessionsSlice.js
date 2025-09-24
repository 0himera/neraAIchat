import { createSlice } from '@reduxjs/toolkit'

const initialState = {
  items: [],
  currentSessionId: null,
}

const sortSessions = items => {
  return items.sort((a, b) => {
    const aTime = a?.updated_at || ''
    const bTime = b?.updated_at || ''
    if (aTime === bTime) return 0
    return bTime.localeCompare(aTime)
  })
}

const sessionsSlice = createSlice({
  name: 'sessions',
  initialState,
  reducers: {
    setSessions(state, action) {
      state.items = sortSessions([...(action.payload || [])])
    },
    upsertSession(state, action) {
      const session = action.payload
      if (!session || !session.session_id) return
      const index = state.items.findIndex(item => item.session_id === session.session_id)
      if (index >= 0) {
        state.items[index] = { ...state.items[index], ...session }
      } else {
        state.items.push(session)
      }
      sortSessions(state.items)
    },
    removeSession(state, action) {
      const id = action.payload
      state.items = state.items.filter(item => item.session_id !== id)
      if (state.currentSessionId === id) {
        state.currentSessionId = state.items[0]?.session_id || null
      }
    },
    setCurrentSession(state, action) {
      state.currentSessionId = action.payload || null
    },
  },
})

export const { setSessions, upsertSession, removeSession, setCurrentSession } = sessionsSlice.actions
export default sessionsSlice.reducer
